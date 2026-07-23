import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
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
from database.db import get_or_create_user, user_exists
from handlers.language_lessons import begin_lesson_feedback, feedback_prompt, parse_lesson_callback


logger = logging.getLogger(__name__)

SEASONAL_BANNERS = {
    "spring": Path("assets/spring.png"),
    "summer": Path("assets/summer.jpg"),
    "autumn": Path("assets/autumn.png"),
    "winter": Path("assets/winter.png"),
}

EXCHANGE_RATE_URLS = {
    "EUR": "https://api.frankfurter.dev/v2/rate/EUR/IRR",
    "USD": "https://api.frankfurter.dev/v2/rate/USD/IRR",
}
EXCHANGE_RATE_CACHE_TTL = timedelta(minutes=30)
_exchange_rate_lock = asyncio.Lock()
_exchange_rate_cache = {
    "fetched_at": None,
    "rates": None,
}

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton(HOME_BUTTON),
            KeyboardButton(MENU_RADAR),
        ],
        [
            KeyboardButton(MENU_CREATE_VITRIN),
            KeyboardButton(MENU_CREATE_HAYAT),
        ],
        [
            KeyboardButton(MENU_PROFILE),
            KeyboardButton(MENU_VIP),
        ],
        [
            KeyboardButton(MENU_SETTINGS),
            KeyboardButton(MENU_HELP),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    is_persistent=True,
)

PERSIAN_DIGITS = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬")


def to_persian_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


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
    return rate


async def get_exchange_rates():
    now_utc = datetime.now(ZoneInfo("UTC"))
    fetched_at = _exchange_rate_cache["fetched_at"]
    cached_rates = _exchange_rate_cache["rates"]

    if fetched_at and cached_rates and now_utc - fetched_at < EXCHANGE_RATE_CACHE_TTL:
        return cached_rates, fetched_at, False

    async with _exchange_rate_lock:
        fetched_at = _exchange_rate_cache["fetched_at"]
        cached_rates = _exchange_rate_cache["rates"]
        now_utc = datetime.now(ZoneInfo("UTC"))
        if fetched_at and cached_rates and now_utc - fetched_at < EXCHANGE_RATE_CACHE_TTL:
            return cached_rates, fetched_at, False

        try:
            euro_rate, dollar_rate = await asyncio.gather(
                asyncio.to_thread(_fetch_rate, "EUR"),
                asyncio.to_thread(_fetch_rate, "USD"),
            )
            fetched_at = datetime.now(ZoneInfo("UTC"))
            rates = {"EUR": euro_rate, "USD": dollar_rate}
            _exchange_rate_cache.update(fetched_at=fetched_at, rates=rates)
            return rates, fetched_at, False
        except Exception:
            logger.exception("Failed to fetch exchange rates")
            if cached_rates and fetched_at:
                return cached_rates, fetched_at, True
            return None, None, False


def format_toman_rate(irr_rate):
    toman_rate = round((irr_rate / 10) / 100) * 100
    return f"{to_persian_digits(f'{toman_rate:,.0f}')} تومان"


def format_date_persian(value):
    return to_persian_digits(value.strftime("%Y-%m-%d"))


def format_time_persian(value):
    return to_persian_digits(value.strftime("%H:%M"))


def build_welcome_text(now, first_name=None, exchange_rates=None, rates_fetched_at=None, rates_stale=False):
    iran_now = now.astimezone(ZoneInfo("Asia/Tehran"))
    jalali = gregorian_to_jalali(now.year, now.month, now.day)
    display_name = (first_name or "کاربر").strip()

    if exchange_rates:
        euro_text = format_toman_rate(exchange_rates["EUR"])
        dollar_text = format_toman_rate(exchange_rates["USD"])
        source_text = "\n📌 منبع: Frankfurter — نرخ مرجع بین‌المللی"
        fetched_spain = rates_fetched_at.astimezone(ZoneInfo("Europe/Madrid")) if rates_fetched_at else now
        update_text = f"\n🕒 آخرین بروزرسانی نرخ: {format_time_persian(fetched_spain)} به وقت اسپانیا"
        stale_text = "\n⚠️ نمایش آخرین نرخ ثبت‌شده؛ دریافت نرخ جدید موقتاً ممکن نیست." if rates_stale else ""
    else:
        euro_text = "موقتاً در دسترس نیست"
        dollar_text = "موقتاً در دسترس نیست"
        source_text = ""
        update_text = ""
        stale_text = "\n⚠️ دریافت نرخ ارز موقتاً ممکن نیست. لطفاً کمی بعد دوباره تلاش کنید."

    gregorian_text = format_date_persian(now)
    jalali_text = to_persian_digits(f"{jalali[0]:04d}-{jalali[1]:02d}-{jalali[2]:02d}")

    return (
        f"درود، {display_name} 👋\n\n"
        f"📅 تاریخ میلادی: {gregorian_text}\n"
        f"🗓 تاریخ شمسی: {jalali_text}\n\n"
        f"🇪🇸 ساعت اسپانیا: {format_time_persian(now)}\n"
        f"🇮🇷 ساعت ایران: {format_time_persian(iran_now)}\n\n"
        f"💶 قیمت یورو: {euro_text}\n"
        f"💵 قیمت دلار: {dollar_text}"
        f"{source_text}"
        f"{update_text}"
        f"{stale_text}\n\n"
        "──────────────\n\n"
        "👤 با تکمیل پروفایل، اخبار، فرصت‌های شغلی، تخفیف‌ها و پیشنهادهای اختصاصی متناسب با شرایط شما برایتان انتخاب و نمایش داده می‌شود.\n\n"
        "✨ ما همچنان در حال توسعه و رفع اشکال ربات هستیم.\n"
        "از همراهی و شکیبایی شما صمیمانه سپاسگزاریم. ✨"
    )


def update_target(update: Update):
    if update.callback_query:
        return update.callback_query.message
    return update.message


async def send_home_dashboard(update: Update, show_banner=False):
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    season = season_for_month(now.month)
    exchange_rates, rates_fetched_at, rates_stale = await get_exchange_rates()
    welcome_text = build_welcome_text(
        now,
        update.effective_user.first_name,
        exchange_rates=exchange_rates,
        rates_fetched_at=rates_fetched_at,
        rates_stale=rates_stale,
    )
    if not show_banner or not await send_start_banner(update, season, welcome_text):
        await update_target(update).reply_text(
            welcome_text,
            reply_markup=MAIN_MENU,
            disable_web_page_preview=True,
        )


async def preview_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Render the first-entry home card without creating a new user."""
    await send_home_dashboard(update, show_banner=True)


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
