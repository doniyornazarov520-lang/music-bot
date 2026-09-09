import os
import threading
import asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.tl.types import InputMessagesFilterMusic

# --- ENVIRONMENT VARIABLES (Render'dan o'qiladi) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Telethon mijozini (Bot rejimida) yaratish
bot = TelegramClient('music_bot_session', API_ID, API_HASH)

# --- RENDER UCHUN FLASK SERVER ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Music Bot is running live via Telethon!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- BOT HANDLERLARI ---
@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    welcome_text = (
        f"Salom, **{event.sender.first_name or 'Foydalanuvchi'}**! 🎧\n\n"
        "Men toza va juda tezkor **Music Bot**man.\n\n"
        "🔹 Qo'shiq nomi yoki ijrochi ismini yozing, men uni kanaldan darhol topib beraman!"
    )
    await event.respond(welcome_text)

@bot.on(events.NewMessage)
async def search_handler(event):
    # Buyruqlarni o'tkazib yuborish
    if event.text.startswith('/'):
        return

    query = event.text.strip().lower()
    if len(query) < 2:
        await event.respond("⚠️ Qidirish uchun kamida 2 ta harf kiriting!")
        return

    status_msg = await event.respond("🔍 Kanaldan qidirilmoqda...")
    found_count = 0

    try:
        # Kanaldan real-vaqtda audio fayllarni qidirish (Direct Search)
        async for message in bot.iter_messages(
            CHANNEL_ID,
            search=query,
            filter=InputMessagesFilterMusic,
            limit=5
        ):
            if message.media:
                found_count += 1
                await bot.send_file(
                    event.chat_id,
                    file=message.media,
                    caption=f"🎧 **{message.file.title or 'Musiqa'}** - {message.file.performer or 'Noma\'lum'}"
                )

        await status_msg.delete()

        if found_count == 0:
            await event.respond("❌ Afsuski, kanaldan bunday musiqa topilmadi.")

    except Exception as e:
        print(f"Qidiruvda xatolik: {e}")
        await status_msg.delete()
        await event.respond("⚠️ Qidiruv jarayonida xatolik yuz berdi.")

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("Telethon Live Search Bot muvaffaqiyatli ishga tushdi...")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
