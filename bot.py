import os
import sqlite3
import secrets
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8274037625:AAGoUwZGo-jqMjB9yie6HK2RxT3qouqVqe4")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Set your admin ID here or via env
DB_PATH = "contents.db"

# Database setup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            unique_code TEXT UNIQUE NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_content(file_id, file_type, unique_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contents (file_id, file_type, unique_code) VALUES (?, ?, ?)",
        (file_id, file_type, unique_code)
    )
    conn.commit()
    conn.close()

def get_content(unique_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_type FROM contents WHERE unique_code = ?", (unique_code,))
    result = cursor.fetchone()
    conn.close()
    return result

# Deletion job
async def delete_messages(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    message_ids = job.data  # List of message IDs to delete
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.error(f"Error deleting message {msg_id}: {e}")

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        if user_id == ADMIN_ID:
            await update.message.reply_text("မင်္ဂလာပါ Admin! Content (Photo/Video/File) တစ်ခုခု ပို့ပေးပါ။ Link generate လုပ်ပေးပါမယ်။")
        else:
            await update.message.reply_text("မင်္ဂလာပါ! ဤ bot သည် link မှတစ်ဆင့် content များ ကြည့်ရှုရန် ဖြစ်ပါသည်။")
        return

    unique_code = args[0]
    content = get_content(unique_code)
    
    if not content:
        await update.message.reply_text("⚠️ တောင်းပန်ပါသည်။ ဤ link သည် မမှန်ကန်တော့ပါ သို့မဟုတ် ဖျက်လိုက်ပါပြီ။")
        return

    file_id, file_type = content
    chat_id = update.effective_chat.id

    # Send content based on type
    try:
        if file_type == "photo":
            sent_msg = await context.bot.send_photo(chat_id=chat_id, photo=file_id)
        elif file_type == "video":
            sent_msg = await context.bot.send_video(chat_id=chat_id, video=file_id)
        elif file_type == "document":
            sent_msg = await context.bot.send_document(chat_id=chat_id, document=file_id)
        else:
            await update.message.reply_text("⚠️ Error: Unknown file type.")
            return

        # Send notification message
        notif_msg = await update.message.reply_text("⚠️ ဤ message သည် 5 မိနစ်အတွင်း အလိုလျှောက် ပျက်သွားပါမည်။")
        
        # Schedule deletion after 5 minutes (300 seconds)
        context.job_queue.run_once(
            delete_messages, 
            when=300, 
            chat_id=chat_id, 
            data=[sent_msg.message_id, notif_msg.message_id]
        )
    except Exception as e:
        logger.error(f"Error sending content: {e}")
        await update.message.reply_text("⚠️ Content ပို့ရာတွင် အမှားအယွင်း ရှိနေပါသည်။")

# Admin content handler
async def handle_admin_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    message = update.message
    file_id = None
    file_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    if file_id:
        unique_code = secrets.token_urlsafe(8)
        save_content(file_id, file_type, unique_code)
        
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={unique_code}"
        
        await message.reply_text(
            f"✅ Content သိမ်းဆည်းပြီးပါပြီ။\n\nLink: `{link}`",
            parse_mode="Markdown"
        )

def main():
    init_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        (filters.PHOTO | filters.VIDEO | filters.Document.ALL) & filters.ChatType.PRIVATE, 
        handle_admin_content
    ))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
