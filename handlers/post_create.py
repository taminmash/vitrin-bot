from telegram import Update
from telegram.ext import ContextTypes


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("TEST")


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return
