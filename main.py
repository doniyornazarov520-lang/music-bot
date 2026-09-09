import os
import threading
import asyncio
from flask import Flask
from telethon import TelegramClient, events
from telethon.tl.types import InputMessagesFilterMusic

# --- SOZLAMALAR ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8748781038:AAHJ8iwZMLMKuZDOZGb_Jko_Uzhl-U_Sri0")
API_ID = int(os.getenv("API_ID", "12345678"))  # my.telegram.org saytidan olinadi
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")

# Kanalingiz username'i (@ bilan) yoki ID'si (-100...)
CHANNEL_ID = os.getenv("CHANNEL_ID", "@sening_kanal_username")

# Telethon mijozini yaratish
client = TelegramClient('bot_session', API_ID, API_HASH)

# --- RENDER UCHUN FLASK SERVER ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Music Bot is running via Telethon Live Search!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- BOT HANDLERLARI ---
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await event.respond(
        "Salom! 🎧\n\n"
        "Qo'shiq nomi yoki ijrochini yozib qidiring, men kanaldan bir zumda topib beraman!"
    )

@client.on(events.NewMessage)
async def search_handler(event):
    if event.text.startswith('/'):
        return

    query = event.text.strip().lower()
    if len(query) < 2:
        await event.respond("⚠️ Kamida 2 ta harf kiriting!")
        return

    status_msg = await event.respond("🔍 Kanaldan qidirilmoqda...")

    found = False
    
    # Kanaldan to'g'ridan-to'g'ri real-vaqtda qidiruv (Live Search)
    async for message in client.iter_messages(
        CHANNEL_ID,
        search=query,
        filter=InputMessagesFilterMusic,
        limit=5
    ):
        if message.media:
            found = True
            await client.send_file(
                event.chat_id,
                file=message.media,
                caption=f"🎧 **{message.file.title or 'Musiqa'}** - {message.file.performer or ''}"
            )

    await status_msg.delete()

    if not found:
        await event.respond("❌ Afsuski, kanaldan bunday musiqa topilmadi.")

async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("Telethon Live Search Bot ishga tushdi...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
