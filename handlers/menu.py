from telegram import Update
from telegram.ext import ContextTypes


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    text = update.message.text

    print("MENU =", text)

    if text == "👤 پروفایل من":

        await update.message.reply_text(
            "تست پروفایل"
        )

    elif text == "🟡 ثبت آگهی در ویترین":

        await update.message.reply_text(
            "تست ویترین"
        )

    elif text == "🟣 ثبت پیام در حیاط خلوت":

        await update.message.reply_text(
            "تست حیاط خلوت"
        )

    elif text == "ℹ️ راهنما":

        await update.message.reply_text(
            "تست راهنما"
        )
