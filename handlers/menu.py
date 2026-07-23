from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import (
    HOME_BUTTON,
    MENU_CREATE_HAYAT,
    MENU_CREATE_VITRIN,
    MENU_HELP,
    MENU_PROFILE,
    MENU_RADAR,
    MENU_SETTINGS,
    MENU_VIP,
)
from handlers.post_create import start_hayat_post, start_post
from handlers.profile import profile_start
from handlers.radar import radar_keyboard, radar_overview_text
from handlers.start import MAIN_MENU, send_home_dashboard


HELP_TEXT = (
    "ℹ️ راهنمای ویترین اسپانیا\n\n"
    "➕ ثبت آگهی:\n"
    "برای ثبت آگهی، روی دکمه «➕ ثبت آگهی» بزنید و مراحل را کامل کنید.\n\n"
    "💬 پیام ناشناس:\n"
    "برای ارسال پیام ناشناس، روی دکمه «💬 پیام ناشناس» بزنید.\n\n"
    "👤 پروفایل:\n"
    "برای دیدن آگهی‌ها، پیش‌نویس‌ها و وضعیت ارسال‌ها.\n\n"
    "📡 رادار:\n"
    "برای دیدن هشدارها، تخفیف‌ها، رویدادها، کار، قوانین و خبرهای کاربردی روز.\n\n"
    "🆘 پشتیبانی:\n"
    "@VitrinSpainAdmin"
)

PLACEHOLDER_BACK_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🏠 صفحه اصلی", callback_data="home:dashboard")]]
)


async def send_placeholder(update: Update, title: str):
    await update.message.reply_text(
        f"{title}\n\nاین بخش در حال توسعه است.",
        reply_markup=PLACEHOLDER_BACK_KEYBOARD,
    )

PUBLIC_BOT_COMMANDS = [
    BotCommand("home", HOME_BUTTON),
    BotCommand("radar", MENU_RADAR),
    BotCommand("create_ad", MENU_CREATE_VITRIN),
    BotCommand("anonymous", MENU_CREATE_HAYAT),
    BotCommand("profile", MENU_PROFILE),
    BotCommand("vip", MENU_VIP),
    BotCommand("settings", MENU_SETTINGS),
    BotCommand("help", MENU_HELP),
]


async def set_public_bot_commands(application):
    await application.bot.set_my_commands(PUBLIC_BOT_COMMANDS)


async def home_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_home_dashboard(update)


async def radar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(radar_overview_text(), reply_markup=radar_keyboard())


async def create_ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_post(update, context, post_type="vitrin")


async def anonymous_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_hayat_post(update, context)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await profile_start(update, context)


async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, MENU_VIP)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_placeholder(update, MENU_SETTINGS)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT,
        reply_markup=MAIN_MENU,
        disable_web_page_preview=True,
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if (
        "profile_step" in context.user_data
        or "post_step" in context.user_data
        or "interaction_step" in context.user_data
    ):
        return

    text = update.message.text

    if text == HOME_BUTTON:
        context.user_data.clear()
        await send_home_dashboard(update)
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

    if text == MENU_RADAR:
        await update.message.reply_text(radar_overview_text(), reply_markup=radar_keyboard())
        return

    if text == MENU_HELP:
        await update.message.reply_text(
            HELP_TEXT,
            reply_markup=MAIN_MENU,
            disable_web_page_preview=True,
        )
        return

    if text == MENU_VIP:
        await send_placeholder(update, "⭐ اشتراک VIP")
        return

    if text == MENU_SETTINGS:
        await send_placeholder(update, "⚙️ تنظیمات")
