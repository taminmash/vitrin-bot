from telegram import ReplyKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes

from config_v2 import WELCOME_TEXT


MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🟡 ثبت آگهی در ویترین"],
        ["🟣 ثبت پیام در حیاط خلوت"],
        ["👤 پروفایل من", "ℹ️ راهنما"],
    ],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=MAIN_MENU,
        disable_web_page_preview=True,
    )
