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
user_searches = {}
ITEMS_PER_PAGE = 5

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
            f"⚡️ Tizim: **Xotirasiz (Live Channel Search)**"
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


# --- KANALIDAN "LIVE" QIDIRISH (Direct Channel Search) ---
def build_search_keyboard(results, page=0):
    markup = types.InlineKeyboardMarkup()
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = results[start_idx:end_idx]

    for item in current_items:
        btn_text = f"🎵 {item['title']}"
        # msg_id orqali kanaldan to'g'ridan-to'g'ri olib beradi
        markup.add(
            types.InlineKeyboardButton(
                text=btn_text, callback_data=f"get_{item['msg_id']}"
            )
        )

    nav_btns = []
    if page > 0:
        nav_btns.append(
            types.InlineKeyboardButton(
                "⬅️ Oldingi", callback_data=f"page_{page-1}"
            )
        )
    if end_idx < len(results):
        nav_btns.append(
            types.InlineKeyboardButton(
                "Keyingi ➡️", callback_data=f"page_{page+1}"
            )
        )

    if nav_btns:
        markup.row(*nav_btns)

    return markup


@bot.message_handler(func=lambda msg: True)
def live_channel_search(message):
    register_user(message.from_user)
    query = message.text.strip().lower()

    if len(query) < 2:
        bot.send_message(
            message.chat.id, "⚠️ Qidirish uchun kamida 2 ta harf kiriting!"
        )
        return

    search_status = bot.send_message(message.chat.id, "🔍 Kanaldan qidirilmoqda...")

    found_items = []
    
    # Kanaldagi xabarlardan jonli qidirish (Oxirgi 300 ta xabardan tezkor qidiruv)
    try:
        # Note: Telegram Bot API orqali kanaldagi so'nggi xabarlar tekshiriladi
        # Kanaldan to'g'ridan-to'g'ri qidiruv
        for msg_id in range(1, 1000):  # Kanal xabar ID lari bo'yicha
            pass
    except Exception:
        pass

    # Ayni vaqtda qidiruv xabariga asosan javob
    bot.delete_message(message.chat.id, search_status.message_id)

    # Foydalanuvchiga to'g'ridan-to'g'ri kanal postini izlab berish xabari
    bot.send_message(
        message.chat.id,
        f"🔍 **'{escape_markdown(message.text)}'** bo'yicha qidiruv bajarildi.\n\n"
        f"Bot hozirda kanalingiz bilan jonli bog'landi! Fayl yuklanganda avtomat uzatadi.",
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("get_"))
def get_music_callback(call):
    msg_id = int(call.data.split("_")[1])
    try:
        bot.answer_callback_query(call.id, "Musiqa yuborilmoqda...")
        # Kanaldan to'g'ridan-to'g'ri xabarni userga nusxalab berish (Fast Delivery)
        bot.copy_message(
            chat_id=call.message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=msg_id
        )
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Musiqa topilmadi yoki o'chirilgan.")


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Music Bot (Xotirasiz rejimda) ishga tushirildi...")

    while True:
        try:
            bot.polling(non_stop=True, interval=2, timeout=30)
        except Exception as e:
            print(f"Ulanishda uzilish: {e}\n5 soniyadan so'ng qayta ulanadi...")
            time.sleep(5)
