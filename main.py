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
# Environment variables orqali o'qish (xavfsizlik uchun)
BOT_TOKEN = os.getenv(
    "BOT_TOKEN", "8748781038:AAHJ8iwZMLMKuZDOZGb_Jko_Uzhl-U_Sri0"
)
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004493023630"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "8216291475"))

bot = telebot.TeleBot(BOT_TOKEN)

MUSIC_FILE = "music_db.json"
USERS_FILE = "users_db.json"

admin_states = {}

# --- RENDER UCHUN FLASK SERVER ---
app = Flask(__name__)


@app.route("/")
def home():
    return "Music Bot is running live!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# --- MARKDOWN BELGILARINI TOZALASH ---
def escape_markdown(text):
    if not text:
        return ""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text))


# --- BAZA BILAN ISHLASH FUNKSIYALARI ---
def load_data(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {} if "users" in file_path else []
                return json.loads(content)
        except Exception as e:
            print(f"Fayl o'qishda xatolik ({file_path}): {e}")
    return {} if "users" in file_path else []


def save_data(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Fayl saqlashda xatolik ({file_path}): {e}")


def register_user(user):
    users = load_data(USERS_FILE)
    user_id = str(user.id)
    if user_id not in users:
        users[user_id] = {
            "name": user.first_name or "Foydalanuvchi",
            "username": user.username or "",
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save_data(USERS_FILE, users)


# --- KANALGA TUSHGAN FAYLNI AVTO-INDEKSASH ---
@bot.channel_post_handler(content_types=["audio", "document", "video"])
def index_channel_audio(message):
    if message.chat.id == CHANNEL_ID:
        music_db = load_data(MUSIC_FILE)

        file_id = None
        title = "Noma'lum qo'shiq"
        performer = "Noma'lum ijrochi"

        if message.audio:
            file_id = message.audio.file_id
            title = (
                message.audio.title or message.caption or "Noma'lum qo'shiq"
            )
            performer = message.audio.performer or "Noma'lum ijrochi"
        elif message.document:
            file_id = message.document.file_id
            title = message.document.file_name or "Noma'lum fayl"
        elif message.video:
            file_id = message.video.file_id
            title = message.caption or "Video / Musiqa"

        if not file_id:
            return

        for item in music_db:
            if item["file_id"] == file_id:
                return

        new_music = {
            "id": len(music_db) + 1,
            "title": title,
            "performer": performer,
            "file_id": file_id,
            "search_text": f"{performer} {title}".lower(),
            "downloads": 0,
        }

        music_db.append(new_music)
        save_data(MUSIC_FILE, music_db)
        print(f"Yangi musiqa bazaga saqlandi: {performer} - {title}")


# --- BOT HANDLERLARI ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
    register_user(message.from_user)
    name = escape_markdown(message.from_user.first_name)
    welcome_text = (
        f"Salom, **{name}**! 🎧\n\n"
        "Men toza va reklamasiz **Music Bot**man.\n\n"
        "🔹 Qo'shiq nomi yoki ijrochi ismini yozib qidiring.\n"
        "🔥 Eng ommabop qo'shiqlarni ko'rish uchun /top buyrug'ini yuboring."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=["stat"])
def stat_cmd(message):
    if message.chat.id == ADMIN_ID:
        users = load_data(USERS_FILE)
        music_db = load_data(MUSIC_FILE)

        msg = (
            f"📊 **Bot Statistikasi:**\n\n"
            f"👤 Foydalanuvchilar: **{len(users)} ta**\n"
            f"🎵 Bazadagi musiqalar: **{len(music_db)} ta**"
        )
        bot.send_message(message.chat.id, msg, parse_mode="Markdown")


@bot.message_handler(commands=["users"])
def list_users_cmd(message):
    if message.chat.id == ADMIN_ID:
        users = load_data(USERS_FILE)
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


@bot.message_handler(commands=["top"])
def top_music_cmd(message):
    register_user(message.from_user)
    music_db = load_data(MUSIC_FILE)

    if not music_db:
        bot.send_message(message.chat.id, "❌ Bazada hali musiqalar yo'q.")
        return

    sorted_music = sorted(
        music_db, key=lambda x: x.get("downloads", 0), reverse=True
    )[:10]

    markup = types.InlineKeyboardMarkup()
    msg_text = "🔥 **Eng ko'p eshitilgan Top-10 qo'shiqlar:**\n\n"

    for idx, item in enumerate(sorted_music, 1):
        downloads = item.get("downloads", 0)
        performer = escape_markdown(item["performer"])
        title = escape_markdown(item["title"])

        msg_text += f"{idx}. **{performer} - {title}** ({downloads} marta)\n"
        markup.add(
            types.InlineKeyboardButton(
                text=f"🎵 {idx}. {item['performer']} - {item['title']}",
                callback_data=f"get_{item['id']}",
            )
        )

    bot.send_message(
        message.chat.id, msg_text, parse_mode="Markdown", reply_markup=markup
    )


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
        "text",
        "photo",
        "audio",
        "voice",
        "video",
        "document",
        "sticker",
    ],
)
def process_broadcast(message):
    if message.text == "/cancel":
        admin_states.pop(ADMIN_ID, None)
        bot.send_message(ADMIN_ID, "❌ Xabar tarqatish bekor qilindi.")
        return

    admin_states.pop(ADMIN_ID, None)
    users = load_data(USERS_FILE)

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


ITEMS_PER_PAGE = 5
user_searches = {}


def build_search_keyboard(results, page=0):
    markup = types.InlineKeyboardMarkup()
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_items = results[start_idx:end_idx]

    for item in current_items:
        btn_text = f"🎵 {item['performer']} - {item['title']}"
        markup.add(
            types.InlineKeyboardButton(
                text=btn_text, callback_data=f"get_{item['id']}"
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
def search_music(message):
    register_user(message.from_user)
    query = message.text.strip().lower()

    if len(query) < 2:
        bot.send_message(
            message.chat.id, "⚠️ Qidirish uchun kamida 2 ta harf kiriting!"
        )
        return

    music_db = load_data(MUSIC_FILE)
    results = [m for m in music_db if query in m["search_text"]]

    if not results:
        bot.send_message(
            message.chat.id,
            "❌ Afsuski, bunday qo'shiq bazadan topilmadi.\nKanalingizga fayl tashlasangiz, bot uni avtomatik bazaga qo'shib oladi!",
        )
        return

    user_searches[str(message.chat.id)] = results
    markup = build_search_keyboard(results, page=0)

    msg_text = (
        f"🔍 **'{escape_markdown(message.text)}'** bo'yicha topilgan natijalar "
        f"(Jami: {len(results)} ta):\n\nEshitmoqchi bo'lgan musiqangizni tanlang:"
    )
    bot.send_message(
        message.chat.id, msg_text, parse_mode="Markdown", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def page_callback(call):
    page = int(call.data.split("_")[1])
    user_id = str(call.message.chat.id)

    results = user_searches.get(user_id, [])
    if not results:
        bot.answer_callback_query(
            call.id, "⚠️ Qidiruv natijasi eskirgan, qaytadan qidiring."
        )
        return

    markup = build_search_keyboard(results, page=page)
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
        )
    except Exception:
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("get_"))
def get_music_callback(call):
    music_id = int(call.data.split("_")[1])
    music_db = load_data(MUSIC_FILE)

    for item in music_db:
        if item["id"] == music_id:
            item["downloads"] = item.get("downloads", 0) + 1
            save_data(MUSIC_FILE, music_db)

            bot.answer_callback_query(call.id, "Yuborilmoqda...")
            bot.send_audio(
                chat_id=call.message.chat.id,
                audio=item["file_id"],
                caption=f"🎧 **{escape_markdown(item['performer'])} - {escape_markdown(item['title'])}**",
                parse_mode="Markdown",
            )
            return

    bot.answer_callback_query(call.id, "❌ Musiqa topilmadi.")


if __name__ == "__main__":
    # Flask serverini fonda yuritish
    threading.Thread(target=run_flask, daemon=True).start()

    print("Music Bot ishga tushirildi...")

    while True:
        try:
            bot.polling(non_stop=True, interval=3, timeout=30)
        except Exception as e:
            print(f"Ulanishda uzilish: {e}\n10 soniyadan so'ng qayta ulanadi...")
            time.sleep(10)
