import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import MENU_CREATE_HAYAT, MENU_CREATE_VITRIN, MENU_HELP, MENU_PROFILE
from handlers.language_lessons import begin_lesson_feedback, feedback_prompt, parse_lesson_callback
from database.db import count_today_dashboard_items, get_or_create_user, user_exists


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

MAIN_MENU = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("💬 پیام ناشناس", callback_data="home:create_hayat"),
            InlineKeyboardButton("➕ ثبت آگهی", callback_data="home:create_vitrin"),
        ],
        [
            InlineKeyboardButton("📡 رادار", callback_data="radar:open"),
            InlineKeyboardButton("👤 پروفایل من", callback_data="home:profile"),
        ],
        [
            InlineKeyboardButton("ℹ️ راهنما", callback_data="home:help"),
            InlineKeyboardButton("🛟 پشتیبانی", callback_data="home:support"),
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
    return {
        "jobs": int(counts.get("jobs") or 0),
        "discounts": int(counts.get("discounts") or 0),
        "events": int(counts.get("events") or 0),
        "radar": int(counts.get("radar") or 0),
        "alerts": int(counts.get("alerts") or 0),
    }


def gregorian_to_jalali(year, month, day):
    """Convert a Gregorian date to Jalali without adding a runtime dependency."""
    days_in_gregorian = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    year_offset = year - 1600
    month_offset = month - 1
    day_offset = day - 1
    day_number = 365 * year_offset + (year_offset + 3) // 4 - (year_offset + 99) // 100 + (year_offset + 399) // 400
    day_number += sum(days_in_gregorian[:month_offset]) + day_offset
    if month_offset > 1 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        day_number += 1
    jalali_days = day_number - 79
    cycles, jalali_days = divmod(jalali_days, 12053)
    jalali_year = 979 + 33 * cycles + 4 * (jalali_days // 1461)
    jalali_days %= 1461
    if jalali_days >= 366:
        jalali_year += (jalali_days - 1) // 365
        jalali_days = (jalali_days - 1) % 365
    if jalali_days < 186:
        jalali_month = 1 + jalali_days // 31
        jalali_day = 1 + jalali_days % 31
    else:
        jalali_month = 7 + (jalali_days - 186) // 30
        jalali_day = 1 + (jalali_days - 186) % 30
    return jalali_year, jalali_month, jalali_day


def build_welcome_text(now, first_name=None):
    counts = dashboard_counts()
    updated_at = now.strftime("%H:%M")
    iran_now = now.astimezone(ZoneInfo("Asia/Tehran"))
    jalali = gregorian_to_jalali(now.year, now.month, now.day)
    display_name = (first_name or "کاربر").strip()

    return (
        f"سلام، {display_name} 👋\n\n"
        f"📅 تاریخ میلادی: {now:%Y-%m-%d}\n"
        f"🗓 تاریخ شمسی: {jalali[0]:04d}-{jalali[1]:02d}-{jalali[2]:02d}\n\n"
        f"🇪🇸 ساعت اسپانیا: {now:%H:%M}\n"
        f"🇮🇷 ساعت ایران: {iran_now:%H:%M}\n\n"
        "💶 قیمت یورو: در دسترس نیست\n"
        "💵 قیمت دلار: در دسترس نیست\n\n"
        "──────────────\n\n"
        "✨ امروز ویترین برای شما محتواهای جدید پیدا کرده است.\n\n"
        f"💼 {counts['jobs']} آگهی شغلی جدید\n"
        f"🛍 {counts['discounts']} تخفیف و آفر\n"
        f"🎉 {counts['events']} رویداد نزدیک شما\n"
        f"📡 {counts['radar']} خبر مهم رادار اسپانیا\n"
        f"🚨 {counts['alerts']} هشدار فوری\n\n"
        "برای دسترسی به این محتواها روی «رادار» کلیک کنید.\n\n"
        f"آخرین بروزرسانی: {updated_at}"
    )


def update_target(update: Update):
    if update.callback_query:
        return update.callback_query.message
    return update.message


async def send_home_dashboard(update: Update, show_banner=False):
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    season = season_for_month(now.month)
    welcome_text = build_welcome_text(now, update.effective_user.first_name)
    if not show_banner or not await send_start_banner(update, season, welcome_text):
        await update_target(update).reply_text(
            welcome_text,
            reply_markup=MAIN_MENU,
            disable_web_page_preview=True,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    first_start = None
    try:
        first_start = not user_exists(update.effective_user.id)
        get_or_create_user(update.effective_user)
    except Exception:
        logger.exception("Failed to create or update user on /start")

    payload = context.args[0] if context.args else None
    if payload and payload.startswith("radar_"):
        from handlers.radar import open_radar_deep_link

        await open_radar_deep_link(update, payload.removeprefix("radar_"))
        return

    if payload and payload.startswith("lesson-"):
        parts = payload.split("-")
        if len(parts) >= 4 and parts[1] in {"comment", "report"}:
            action = parts[1]
            level = "-".join(parts[2:-1])
            parsed = parse_lesson_callback(f"lesson:{action}:{level}:{parts[-1]}")
            if parsed:
                begin_lesson_feedback(context, action, parsed.level, parsed.lesson_number)
                await update.message.reply_text(feedback_prompt(action, parsed.lesson_number))
                return
        logger.warning("Ignoring malformed lesson feedback deep link: %r", payload)

    await send_home_dashboard(update, show_banner=first_start is not False)


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
