from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import MENU_CREATE_HAYAT, MENU_CREATE_VITRIN, MENU_HELP, MENU_PROFILE, WELCOME_TEXT


MAIN_MENU = ReplyKeyboardMarkup(
    [
        [MENU_CREATE_VITRIN],
        [MENU_CREATE_HAYAT],
        [MENU_PROFILE, MENU_HELP],
    ],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=MAIN_MENU,
        disable_web_page_preview=True,
    )
