from datetime import datetime
import json
import os
import re
import threading
import time
from flask import Flask
import telebot
from telebot import types

# --- ASOSIY SOZLAMALAR ---
BOT_TOKEN = os.getenv(
    "BOT_TOKEN", "8748781038:AAHJ8iwZMLMKuZDOZGb_Jko_Uzhl-U_Sri0"
)
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004493023630"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8216291475"))

bot = telebot.TeleBot(BOT_TOKEN)

USERS_FILE = "users_db.json"
admin_states = {}

# --- RENDER UCHUN FLASK SERVER ---
app = Flask(__name__)


@app.route("/")
def home():
    return "Music Bot is running live without database!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# --- MARKDOWN BELGILARINI TOZALASH ---
def escape_markdown(text):
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


# --- FOYDALANUVCHILARNI SAQLASH (Statistika uchun) ---
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            print(f"Foydalanuvchilarni o'qishda xatolik: {e}")
    return {}


def save_users(data):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Foydalanuvchilarni saqlashda xatolik: {e}")


def register_user(user):
    users = load_users()
    user_id = str(user.id)
    if user_id not in users:
        users[user_id] = {
            "name": user.first_name or "Foydalanuvchi",
            "username": user.username or "",
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save_users(users)


# --- BOT HANDLERLARI ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
    register_user(message.from_user)
    name = escape_markdown(message.from_user.first_name)
    welcome_text = (
        f"Salom, **{name}**! 🎧\n\n"
        "Men toza va tezkor **Music Bot**man.\n\n"
        "🔹 Qo'shiq nomi yoki ijrochi ismini yozing, men uni kanaldan izlab topaman!"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=["stat"])
def stat_cmd(message):
    if message.chat.id == ADMIN_ID:
        users = load_users()
        msg = (
            f"📊 **Bot Statistikasi:**\n\n"
            f"👤 Foydalanuvchilar: **{len(users)} ta**\n"
            f"⚡️ Tizim: **Direct Channel Search (Xotirasiz)**"
        )
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")


@bot.message_handler(commands=["users"])
def list_users_cmd(message):
    if message.chat.id == ADMIN_ID:
        users = load_users()
        if not users:
            bot.send_message(
                message.chat.id, "❌ Hali hech kim botdan foydalanmadi."
            )
            return

        msg = "👥 **Foydalanuvchilar ro'yxati:**\n\n"
        for idx, (u_id, u_info) in enumerate(users.items(), 1):
            safe_name = escape_markdown(u_info.get("name", "Foydalanuvchi"))
            username = u_info.get("username", "")
            safe_user = (
                f"@{escape_markdown(username)}" if username else "Username yo'q"
            )

            msg += f"{idx}. **{safe_name}** ({safe_user}) — ID: `{u_id}`\n"

            if idx >= 50:
                msg += (
                    "\n⚠️ *Faqat birinchi 50 ta foydalanuvchi ko'rsatildi.*"
                )
                break

        bot.send_message(message.chat.id, msg, parse_mode="Markdown")


@bot.message_handler(commands=["send"])
def start_broadcast(message):
    if message.chat.id == ADMIN_ID:
        admin_states[ADMIN_ID] = "WAITING_FOR_BROADCAST_MSG"
        bot.send_message(
            ADMIN_ID,
            "📢 **Xabar tarqatish rejimidasiz.**\n\n"
            "Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
            "Bekor qilish uchun /cancel deb yozing.",
            parse_mode="Markdown",
        )


@bot.message_handler(
    func=lambda msg: msg.chat.id == ADMIN_ID
    and admin_states.get(ADMIN_ID) == "WAITING_FOR_BROADCAST_MSG",
    content_types=[
        "text", "photo", "audio", "voice", "video", "document", "sticker"
    ],
)
def process_broadcast(message):
    if message.text == "/cancel":
        admin_states.pop(ADMIN_ID, None)
        bot.send_message(ADMIN_ID, "❌ Xabar tarqatish bekor qilindi.")
        return

    admin_states.pop(ADMIN_ID, None)
    users = load_users()

    status_msg = bot.send_message(
        ADMIN_ID, "🚀 Xabar tarqatish boshlandi, kuting..."
    )

    success = 0
    failed = 0

    for user_id in users.keys():
        try:
            bot.copy_message(
                chat_id=int(user_id),
                from_chat_id=ADMIN_ID,
                message_id=message.message_id,
            )
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    bot.edit_message_text(
        chat_id=ADMIN_ID,
        message_id=status_msg.message_id,
        text=f"✅ **Xabar tarqatish yakunlandi!**\n\n"
        f"🟢 Muvaffaqiyatli yetkazildi: **{success} ta**\n"
        f"🔴 Etib bormadi: **{failed} ta**",
        parse_mode="Markdown",
    )


# --- KANALGA YANGI FAYL TUSHGANDA ESHITISH ---
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    if message.chat.id == CHANNEL_ID:
        print(f"Kanalga yangi musiqa joylandi, ID: {message.message_id}")


# --- KANALIDAN TO'G'RIDAN-TO'G'RI QIDIRUV ---
@bot.message_handler(func=lambda msg: True)
def search_music_direct(message):
    register_user(message.from_user)
    query = message.text.strip().lower()

    if len(query) < 2:
        bot.send_message(
            message.chat.id, "⚠️ Qidirish uchun kamida 2 ta harf kiriting!"
        )
        return

    status_msg = bot.send_message(message.chat.id, "🔍 Kanaldan qidirilmoqda...")
    found = False

    try:
        # Oxirgi 200 ta post ichidan tezkor izlash
        start_id = message.message_id
        end_id = max(1, start_id - 200)

        for msg_id in range(start_id, end_id, -1):
            try:
                # Xabarni admin chatiga vaqtinchalik nusxalab ko'rish
                forwarded = bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=CHANNEL_ID,
                    message_id=msg_id,
                    disable_notification=True
                )

                if forwarded.audio:
                    title = (forwarded.audio.title or "").lower()
                    performer = (forwarded.audio.performer or "").lower()
                    caption = (forwarded.caption or "").lower()

                    if query in title or query in performer or query in caption:
                        # Topilgan musiqani foydalanuvchiga yuborish
                        bot.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=CHANNEL_ID,
                            message_id=msg_id
                        )
                        found = True

                # Vaqtinchalik xabarni admin chatidan o'chirish
                bot.delete_message(ADMIN_ID, forwarded.message_id)

                if found:
                    break

            except Exception:
                continue

    except Exception as e:
        print(f"Qidiruvda xatolik: {e}")

    try:
        bot.delete_message(message.chat.id, status_msg.message_id)
    except Exception:
        pass

    if not found:
        bot.send_message(
            message.chat.id, "❌ Afsuski, kanaldan bunday musiqa topilmadi."
        )


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Music Bot (Xotirasiz rejimda) ishga tushirildi...")

    while True:
        try:
            bot.polling(non_stop=True, interval=2, timeout=30)
        except Exception as e:
            print(f"Ulanishda uzilish: {e}\n5 soniyadan so'ng qayta ulanadi...")
            time.sleep(5)
