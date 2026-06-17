from telegram import Update
from telegram.ext import ContextTypes

from handlers.admin import send_post_to_admin


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["post_step"] = "test"

    await update.message.reply_text(
        "ثبت آگهی تستی"
    )


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "post_step" not in context.user_data:
        return

    await update.message.reply_text(
        "post handler ok"
    )

    context.user_data.clear()
