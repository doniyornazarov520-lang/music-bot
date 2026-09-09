import os
import sqlite3
import threading
import time
from flask import Flask
import telebot
import yt_dlp

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- BAZA BILAN ISHLASH (SQLite) ---
def init_db():
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS music (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE,
            title TEXT,
            performer TEXT,
            query_text TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def add_music_to_db(message_id, title, performer, caption=""):
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    query_text = f"{title} {performer} {caption}".lower()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO music (message_id, title, performer, query_text) VALUES (?, ?, ?, ?)",
            (message_id, title, performer, query_text)
        )
        conn.commit()
    except Exception as e:
        print(f"Baza xatosi: {e}")
    finally:
        conn.close()

def search_music_in_db(query):
    conn = sqlite3.connect("music.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM music WHERE query_text LIKE ?", (f"%{query.lower()}%",))
    results = cursor.fetchall()
    conn.close()
    return [r[0] for r in results]

# --- RENDER FLASK SERVER ---
@app.route("/")
def home():
    return "Music Auto-Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- BOT HANDLERLARI ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
    welcome_text = (
        f"Salom, **{message.from_user.first_name}**! 🎧\n\n"
        "Men avtomatik va tezkor **Music Bot**man.\n\n"
        "🔹 Qo'shiq nomi yoki artistni yozing, men uni kanaldan topib beraman!\n\n"
        "💡 *Adminlar uchun:* `/add qo'shiq nomi` - YouTube'dan avto-yuklab kanalga joylash."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# ADMIN UCHUN: Avtomatik yuklab kanalga joylash
@bot.message_handler(commands=["add"])
def add_music_auto(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⚠️ Bu buyruq faqat Admin uchun!")
        return

    song_name = message.text.replace("/add", "").strip()
    if not song_name:
        bot.send_message(
            message.chat.id,
            "⚠️ Qo'shiq nomini yozing: `/add Toshkent`",
            parse_mode="Markdown",
        )
        return

    status = bot.send_message(
        message.chat.id, f"📥 **'{song_name}'** qidirilmoqda..."
    )

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "song.%(ext)s",
        "extractor_args": {
            "youtube": {"player_client": ["ios", "android", "web_creator"]}
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # YouTube va SoundCloud'dan izlash
            try:
                info = ydl.extract_info(
                    f"ytsearch1:{song_name}", download=True
                )["entries"][0]
            except Exception:
                # Agar YouTube bloklasa, SoundCloud'ga o'tish
                info = ydl.extract_info(
                    f"scsearch1:{song_name}", download=True
                )["entries"][0]

            filename = "song.mp3"
            title = info.get("title", "Musiqa")
            uploader = info.get("uploader", "Unknown")

        bot.edit_message_text(
            f"📤 Kanalga joylanmoqda: **{title}**",
            message.chat.id,
            status.message_id,
            parse_mode="Markdown",
        )

        with open(filename, "rb") as audio:
            sent_msg = bot.send_audio(
                CHANNEL_ID,
                audio,
                title=title,
                performer=uploader,
                caption=f"🎧 {title}\n🤖 @{bot.get_me().username}",
            )

        # Bazaga qo'shish
        add_music_to_db(sent_msg.message_id, title, uploader)

        if os.path.exists(filename):
            os.remove(filename)

        bot.send_message(
            message.chat.id, "✅ Musiqa kanalga joylandi va bazaga saqlandi!"
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Yuklashda xatolik yuz berdi: {e}")

# KANALGA QO'LDA MUSIQA TASHLANGANDA HAM BAZAGA YOZISH
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    if message.chat.id == CHANNEL_ID and message.audio:
        title = message.audio.title or ""
        performer = message.audio.performer or ""
        caption = message.caption or ""
        add_music_to_db(message.message_id, title, performer, caption)

# QIDIRUV HANDLERI
@bot.message_handler(func=lambda msg: True)
def search_music(message):
    query = message.text.strip()
    if len(query) < 2 or query.startswith('/'):
        return

    msg_ids = search_music_in_db(query)

    if not msg_ids:
        bot.send_message(message.chat.id, "❌ Afsuski, kanaldan bunday musiqa topilmadi.")
        return

    status = bot.send_message(message.chat.id, "🔍 Musiqa yuborilmoqda...")
    found = 0

    for m_id in msg_ids[:5]:
        try:
            bot.copy_message(message.chat.id, CHANNEL_ID, m_id)
            found += 1
        except Exception as e:
            print(f"Yuborishda xatolik: {e}")

    bot.delete_message(message.chat.id, status.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot ishga tushdi...")
    while True:
        try:
            bot.polling(non_stop=True, interval=1, timeout=30)
        except Exception as e:
            time.sleep(5)
