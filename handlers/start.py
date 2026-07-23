import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import get_or_create_user, user_exists
from handlers.language_lessons import begin_lesson_feedback, feedback_prompt, parse_lesson_callback


logger = logging.getLogger(__name__)

SEASONAL_BANNERS = {
    "spring": Path("assets/spring.png"),
    "summer": Path("assets/summer.jpg"),
    "autumn": Path("assets/autumn.png"),
    "winter": Path("assets/winter.png"),
}

MENU_RADAR = "📡 اخبار اختصاصی شما"
MENU_CREATE_VITRIN_DASHBOARD = "➕ ثبت آگهی در ویترین"
MENU_CREATE_HAYAT_DASHBOARD = "💬 پیام ناشناس در حیات خلوت"

EXCHANGE_RATE_URLS = {
    "EUR": "https://api.frankfurter.dev/v2/rate/EUR/IRR",
    "USD": "https://api.frankfurter.dev/v2/rate/USD/IRR",
}
EXCHANGE_RATE_CACHE_TTL = timedelta(minutes=30)
_exchange_rate_cache = {
    "fetched_at": None,
    "rates": None,
    "date": None,
}

MAIN_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(MENU_RADAR, callback_data="radar:open")],
        [InlineKeyboardButton(MENU_CREATE_VITRIN_DASHBOARD, callback_data="home:create_vitrin")],
        [InlineKeyboardButton(MENU_CREATE_HAYAT_DASHBOARD, callback_data="home:create_hayat")],
        [InlineKeyboardButton("👤 پروفایل من", callback_data="home:profile")],
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


def _fetch_rate(currency):
    request = Request(
        EXCHANGE_RATE_URLS[currency],
        headers={"User-Agent": "VitrinSpainBot/1.0"},
    )
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)

    rate = float(payload["rate"])
    if rate <= 0:
        raise ValueError(f"Invalid {currency}/IRR rate: {rate}")
    return rate, payload.get("date")


async def get_exchange_rates():
    now_utc = datetime.now(ZoneInfo("UTC"))
    fetched_at = _exchange_rate_cache["fetched_at"]
    cached_rates = _exchange_rate_cache["rates"]

    if fetched_at and cached_rates and now_utc - fetched_at < EXCHANGE_RATE_CACHE_TTL:
        return cached_rates, _exchange_rate_cache["date"]

    try:
        eur_result, usd_result = await asyncio.gather(
            asyncio.to_thread(_fetch_rate, "EUR"),
            asyncio.to_thread(_fetch_rate, "USD"),
        )
        rates = {"EUR": eur_result[0], "USD": usd_result[0]}
        source_date = eur_result[1] or usd_result[1]
        _exchange_rate_cache.update(
            fetched_at=now_utc,
            rates=rates,
            date=source_date,
        )
        return rates, source_date
    except Exception:
        logger.exception("Failed to fetch exchange rates")
        if cached_rates:
            return cached_rates, _exchange_rate_cache["date"]
        return None, None


def format_toman_rate(irr_rate):
    toman_rate = round(irr_rate / 10)
    return f"{toman_rate:,.0f} تومان"


def build_welcome_text(now, first_name=None, exchange_rates=None, rate_date=None):
    iran_now = now.astimezone(ZoneInfo("Asia/Tehran"))
    jalali = gregorian_to_jalali(now.year, now.month, now.day)
    display_name = (first_name or "کاربر").strip()
    updated_at = now.strftime("%H:%M")

    if exchange_rates:
        euro_text = format_toman_rate(exchange_rates["EUR"])
        dollar_text = format_toman_rate(exchange_rates["USD"])
        source_suffix = " (مرجع بین‌المللی Frankfurter)"
        rate_date_text = f"\n📌 تاریخ نرخ مرجع: {rate_date}" if rate_date else ""
    else:
        euro_text = "موقتاً در دسترس نیست"
        dollar_text = "موقتاً در دسترس نیست"
        source_suffix = ""
        rate_date_text = ""

    return (
        f"درود، {display_name} 👋\n\n"
        f"📅 تاریخ میلادی: {now:%Y-%m-%d}\n"
        f"🗓 تاریخ شمسی: {jalali[0]:04d}-{jalali[1]:02d}-{jalali[2]:02d}\n\n"
        f"🇪🇸 ساعت اسپانیا: {now:%H:%M}\n"
        f"🇮🇷 ساعت ایران: {iran_now:%H:%M}\n\n"
        f"💶 قیمت یورو{source_suffix}: {euro_text}\n"
        f"💵 قیمت دلار{source_suffix}: {dollar_text}"
        f"{rate_date_text}\n\n"
        "──────────────\n\n"
        "👤 با تکمیل پروفایل، اخبار، فرصت‌های شغلی، تخفیف‌ها و پیشنهادهای اختصاصی متناسب با شرایط شما برایتان انتخاب و نمایش داده می‌شود.\n\n"
        "✨ ما همچنان در حال توسعه و رفع اشکال ربات هستیم.\n"
        "از همراهی و شکیبایی شما صمیمانه سپاسگزاریم. ✨\n\n"
        f"🕒 آخرین بروزرسانی: {updated_at} به وقت اسپانیا"
    )


def update_target(update: Update):
    if update.callback_query:
        return update.callback_query.message
    return update.message


async def send_home_dashboard(update: Update, show_banner=False):
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    season = season_for_month(now.month)
    exchange_rates, rate_date = await get_exchange_rates()
    welcome_text = build_welcome_text(
        now,
        update.effective_user.first_name,
        exchange_rates=exchange_rates,
        rate_date=rate_date,
    )
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
