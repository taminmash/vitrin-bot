from telegram import Update
from telegram.ext import ContextTypes

from config_v2 import HOME_BUTTON, MENU_CREATE_HAYAT, MENU_CREATE_VITRIN, MENU_HELP, MENU_PROFILE
from handlers.common import home_keyboard
from handlers.post_create import start_hayat_post, start_post
from handlers.profile import profile_start
from handlers.start import MAIN_MENU


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if "profile_step" in context.user_data or "post_step" in context.user_data:
        return

    text = update.message.text

    if text == HOME_BUTTON:
        context.user_data.clear()
        await update.message.reply_text(
            "به منوی اصلی برگشتید.",
            reply_markup=MAIN_MENU,
        )
        return

    if text == MENU_CREATE_VITRIN:
        await start_post(update, context, post_type="vitrin")
        return

    if text == MENU_CREATE_HAYAT:
        await start_hayat_post(update, context)
        return

    if text == MENU_PROFILE:
        await profile_start(update, context)
        return

    if text == MENU_HELP:
        await update.message.reply_text(
            "برای ثبت آگهی، گزینه «ثبت آگهی در ویترین» را انتخاب کنید و مراحل را کامل کنید.",
            reply_markup=home_keyboard(),
        )
