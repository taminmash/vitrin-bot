import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import MENU_CREATE_HAYAT, MENU_CREATE_VITRIN, MENU_HELP, MENU_PROFILE
from database.db import get_or_create_user


logger = logging.getLogger(__name__)

SEASONAL_BANNERS = {
    "spring": Path("assets/spring.png"),
    "summer": Path("assets/summer.png"),
    "autumn": Path("assets/autumn.png"),
    "winter": Path("assets/winter.png"),
}

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [MENU_CREATE_VITRIN],
        [MENU_CREATE_HAYAT],
        [MENU_PROFILE, MENU_HELP],
    ],
    resize_keyboard=True,
)

GREGORIAN_MONTHS_FA = {
    1: "ژانویه",
    2: "فوریه",
    3: "مارس",
    4: "آوریل",
    5: "مه",
    6: "ژوئن",
    7: "ژوئیه",
    8: "اوت",
    9: "سپتامبر",
    10: "اکتبر",
    11: "نوامبر",
    12: "دسامبر",
}

JALALI_MONTHS_FA = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند",
}

SEASON_GREETINGS = {
    "winter": "زمستانتان گرم و پرامید",
    "spring": "بهارتان تازه و پرخبرهای خوب",
    "summer": "تابستانتان روشن و پرانرژی",
    "autumn": "پاییزتان آرام و پربرکت",
}


def gregorian_to_jalali(gy, gm, gd):
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy -= 1600
    gm -= 1
    gd -= 1

    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((gy + 1600) % 4 == 0 and ((gy + 1600) % 100 != 0 or (gy + 1600) % 400 == 0)):
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 0
    while jm < 11 and j_day_no >= j_days_in_month[jm]:
        j_day_no -= j_days_in_month[jm]
        jm += 1

    return jy, jm + 1, j_day_no + 1


def season_for_month(month):
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def build_welcome_text(now, first_name=None):
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)

    jalali_date = f"{jd} {JALALI_MONTHS_FA[jm]} {jy}"
    gregorian_date = f"{now.day} {GREGORIAN_MONTHS_FA[now.month]} {now.year}"
    spain_time = now.strftime("%H:%M")
    greeting_name = first_name or "دوست عزیز"

    return (
        "🇪🇸 Vitrin Spain OS\n\n"
        f"👋 سلام، {greeting_name}\n"
        "خوش آمدی.\n\n"
        f"📅 تاریخ شمسی: {jalali_date}\n"
        f"📅 تاریخ میلادی: {gregorian_date}\n"
        f"🕒 ساعت اسپانیا: {spain_time}\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "💶 یورو: به‌زودی\n"
        "💵 دلار: به‌زودی\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "✨ همه نیازها، در جامع‌ترین پلتفرم دیجیتال اسپانیا برای فارسی‌زبانان ✨\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ در حال حاضر بخش «ثبت آگهی در ویترین» و «ثبت پیام ناشناس در حیاط خلوت» فعال است.\n\n"
        "سایر بخش‌ها در حال طراحی، توسعه و کدنویسی هستند و به‌زودی تکمیل خواهند شد.\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🆘 پشتیبانی:\n"
        "@VitrinSpainAdmin"
    )


async def send_home_dashboard(update: Update):
    now = datetime.now(ZoneInfo("Europe/Madrid"))
    welcome_text = build_welcome_text(now, update.effective_user.first_name)
    await update.message.reply_text(
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
    await send_home_dashboard(update)


async def send_start_banner(update: Update, season: str, caption: str):
    image_path = SEASONAL_BANNERS[season]
    if not image_path.exists():
        return False

    try:
        with image_path.open("rb") as image:
            await update.message.reply_photo(
                photo=image,
                caption=caption,
                reply_markup=MAIN_MENU,
            )
        return True
    except Exception:
        return False
