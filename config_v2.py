import os


BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

def parse_int_list(value, fallback):
    if not value:
        return fallback
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_int(value, fallback):
    return int(value) if value else fallback


ADMIN_IDS = parse_int_list(os.getenv("ADMIN_USER_IDS"), [8747305714])
PAID_USER_IDS = parse_int_list(os.getenv("PAID_USER_IDS"), [])

TECH_SUPPORT_IDS = [
    41792255,
]

CHANNEL_VITRIN = parse_int(os.getenv("VITRIN_CHANNEL_ID"), -1003945260173)
CHANNEL_HAYAT = parse_int(os.getenv("HAYAT_CHANNEL_ID"), -1003854428039)
CHANNEL_VITRIN_LINK = "https://t.me/vitrinspain"
CHANNEL_HAYAT_LINK = "https://t.me/hayatkhalvatspain"
CHANNEL_VITRIN_USERNAME = "@vitrinspain"
CHANNEL_HAYAT_USERNAME = "@hayatkhalvatspain"

BOT_USERNAME = os.getenv("BOT_USERNAME", "VitrinSpainBot")
PROJECT_NAME = "ویترین اسپانیا"

BACK_BUTTON = "⬅️ بازگشت به صفحه قبلی"
HOME_BUTTON = "🏠 بازگشت به صفحه اصلی"
MENU_CREATE_VITRIN = "🟡 ثبت آگهی در ویترین"
MENU_CREATE_HAYAT = "🟣 ثبت پیام در حیاط خلوت"
MENU_PROFILE = "👤 پروفایل من"
MENU_HELP = "ℹ️ راهنما"

WELCOME_TEXT = (
    "اولین و کامل‌ترین مجموعه دیجیتالی اسپانیا برای همه فارسی‌زبانان\n\n"
    f"کانال ویترین:\n{CHANNEL_VITRIN_LINK}\n\n"
    f"کانال حیاط خلوت:\n{CHANNEL_HAYAT_LINK}\n\n"
    "پشتیبانی:\n@VitrinSpainAdmin"
)

SUBCATEGORIES = {
    "💼 کار و درآمد": [
        "📂 استخدام",
        "📂 جستجوی کار",
        "📂 خدمات فریلنسری",
        "📂 همکاری و مشارکت",
    ],
    "🏠 خانه و اجاره": [
        "📂 اجاره خانه",
        "📂 اجاره اتاق",
        "📂 هم‌خانه",
        "📂 خرید و فروش ملک",
    ],
    "🛒 خرید و فروش": [
        "📂 لوازم خانه",
        "📂 موبایل و کامپیوتر",
        "📂 خودرو",
        "📂 سایر",
    ],
    "🔧 خدمات": [
        "📂 خدمات حقوقی",
        "📂 خدمات مهاجرت",
        "📂 خدمات فنی",
        "📂 سایر خدمات",
    ],
    "🚚 ارسال بار": [
        "📂 اسپانیا به ایران",
        "📂 ایران به اسپانیا",
        "📂 مسافر و بار",
    ],
    "💰 سرمایه‌گذاری": [
        "📂 سرمایه‌گذاری",
        "📂 شراکت",
        "📂 کسب و کار",
    ],
    "💶 خرید و فروش یورو": [
        "📂 خرید یورو",
        "📂 فروش یورو",
    ],
    "📢 آگهی ویژه": [
        "📂 تبلیغات",
        "📂 معرفی کسب و کار",
    ],
}

CATEGORY_OPTIONS = [
    "🏠 املاک",
    "💼 کار و استخدام",
    "🛠 خدمات",
    "🛍 خرید و فروش",
    "🚚 ارسال بار",
    "📦 سایر",
]
