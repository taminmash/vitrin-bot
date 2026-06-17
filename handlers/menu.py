from telegram import Update
from telegram.ext import ContextTypes

from handlers.profile import profile_start
from handlers.post_create import start_post


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    text = update.message.text

    if text == "🟡 ثبت آگهی در ویترین":

        await update.message.reply_text(
            "ورود به ثبت آگهی"
        )

    elif text == "🟣 ثبت پیام در حیاط خلوت":

        await update.message.reply_text(
            "ورود به حیاط خلوت"
        )

    elif text == "👤 پروفایل من":

        await profile_start(update, context)

    elif text == "ℹ️ راهنما":

        await update.message.reply_text(
            "راهنمای ویترین اسپانیا به زودی تکمیل می‌شود."
        )
