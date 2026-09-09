import os
import threading
import time
from flask import Flask
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)

# Musiqalarni xotirada saqlash uchun lug'at (In-Memory Database)
# { message_id: {"title": "...", "performer": "...", "caption": "..."} }
music_index = {}

app = Flask(__name__)

@app.route("/")
def home():
    return "Music Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# START BUYRUG'I
@bot.message_handler(commands=["start"])
def start_cmd(message):
    welcome_text = (
        f"Salom, **{message.from_user.first_name}**! 🎧\n\n"
        "Men tezkor **Music Bot**man.\n\n"
        "🔹 Qo'shiq nomi yoki ijrochi ismini yozing, men uni kanaldan topib beraman!"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

# KANALGA YANGI MUSIQA TUSHDANIDA UNI INDEKSGA QO'SHISH
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    if message.chat.id == CHANNEL_ID and message.audio:
        title = (message.audio.title or "").lower()
        performer = (message.audio.performer or "").lower()
        caption = (message.caption or "").lower()

        music_index[message.message_id] = {
            "title": title,
            "performer": performer,
            "caption": caption
        }
        print(f"Yangi musiqa indekslandi: {message.message_id}")

# FOYDALANUVCHI QIDIRGANDA
@bot.message_handler(func=lambda msg: True)
def search_music(message):
    query = message.text.strip().lower()

    if len(query) < 2:
        bot.send_message(message.chat.id, "⚠️ Qidirish uchun kamida 2 ta harf kiriting!")
        return

    status_msg = bot.send_message(message.chat.id, "🔍 Kanaldan qidirilmoqda...")
    found_count = 0

    # Saqlangan musiqalar orasidan qidirish
    for msg_id, data in list(music_index.items()):
        if query in data["title"] or query in data["performer"] or query in data["caption"]:
            try:
                bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=CHANNEL_ID,
                    message_id=msg_id
                )
                found_count += 1
                if found_count >= 5:
                    break
            except Exception as e:
                print(f"Musiqa yuborishda xatolik: {e}")

    try:
        bot.delete_message(message.chat.id, status_msg.message_id)
    except Exception:
        pass

    if found_count == 0:
        bot.send_message(
            message.chat.id, 
            "❌ Afsuski, kanaldan bunday musiqa topilmadi.\n\n"
            "💡 *Eslatma: Bot faqat u ishga tushganidan keyin va kanalga yangi joylangan musiqalarni qidira oladi.*",
            parse_mode="Markdown"
        )

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot ishga tushdi...")
    
    while True:
        try:
            bot.polling(non_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Xatolik: {e}")
            time.sleep(5)
