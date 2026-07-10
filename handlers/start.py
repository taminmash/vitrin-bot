import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import MENU_CREATE_HAYAT, MENU_CREATE_VITRIN, MENU_HELP, MENU_PROFILE
from database.db import count_today_dashboard_items, get_or_create_user


logger = logging.getLogger(__name__)

SEASONAL_BANNERS = {
    "spring": Path("assets/spring.png"),
    "summer": Path("assets/summer.jpg"),
    "autumn": Path("assets/autumn.png"),
    "winter": Path("assets/winter.png"),
}

MENU_RADAR = "📡 رادار اسپانیا"
MENU_CREATE_VITRIN_DASHBOARD = "➕ ثبت آگهی در ویترین"
MENU_CREATE_HAYAT_DASHBOARD = "💬 پیام ناشناس حیاط خلوت"

DEMO_DASHBOARD_COUNTS = {
    "jobs": 3,
    "discounts": 5,
    "events": 2,
    "radar": 4,
    "alerts": 1,
}

MAIN_MENU = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(MENU_CREATE_VITRIN_DASHBOARD, callback_data="home:create_vitrin"),
            InlineKeyboardButton(MENU_CREATE_HAYAT_DASHBOARD, callback_data="home:create_hayat"),
        ],
        [InlineKeyboardButton(MENU_RADAR, callback_data="radar:open")],
        [
            InlineKeyboardButton(MENU_HELP, callback_data="home:help"),
            InlineKeyboardButton(MENU_PROFILE, callback_data="home:profile"),
        ],
    ]
)


def season_for_month(month):
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def dashboard_counts():
    try:
        counts = count_today_dashboard_items()
    except Exception:
        logger.exception("Failed to load dashboard counts")
        counts = {}
    return {**DEMO_DASHBOARD_COUNTS, **{key: value for key, value in counts.items() if value}}


def build_welcome_text(now, first_name=None):
    counts = dashboard_counts()
    updated_at = now.strftime("%H:%M")

    return (
        "✨ امروز ویترین برای شما فرصت‌های جدید پیدا کرده است.\n\n"
        f"💼 {counts['jobs']} آگهی شغلی جدید\n"
        f"🛍 {counts['discounts']} تخفیف و آفر\n"
        f"🎉 {counts['events']} رویداد نزدیک شما\n"
        f"📡 {counts['radar']} خبر مهم رادار اسپانیا\n"
        f"🚨 {counts['alerts']} هشدار فوری\n\n"
        f"آخرین بروزرسانی: {updated_at}"
    )


def update_target(update: Update):
    if update.callback_query:
        return update.callback_query.message
    return update.message


async def send_home_dashboard(update: Update):
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    season = season_for_month(now.month)
    welcome_text = build_welcome_text(now, update.effective_user.first_name)
    if not await send_start_banner(update, season, welcome_text):
        await update_target(update).reply_text(
            welcome_text,
            reply_markup=MAIN_MENU,
            disable_web_page_preview=True,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    try:
        get_or_create_user(update.effective_user)
    except Exception:
        logger.exception("Failed to create or update user on /start")

    payload = context.args[0] if context.args else None
    if payload and payload.startswith("radar_"):
        from handlers.radar import open_radar_deep_link

        await open_radar_deep_link(update, payload.removeprefix("radar_"))
        return

    await send_home_dashboard(update)


async def send_start_banner(update: Update, season: str, caption: str):
    image_path = SEASONAL_BANNERS[season]
    if not image_path.exists():
        return False

    try:
        with image_path.open("rb") as image:
            await update_target(update).reply_photo(
                photo=image,
                caption=caption,
                reply_markup=MAIN_MENU,
            )
        return True
    except Exception:
        logger.exception("Failed to send start banner")
        return False
