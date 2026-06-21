import os


BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_IDS = [
    8747305714,
]

TECH_SUPPORT_IDS = [
    41792255,
]

CHANNEL_VITRIN = -1003945260173
CHANNEL_HAYAT = -1003854428039
CHANNEL_VITRIN_LINK = "https://t.me/vitrinspain"
CHANNEL_HAYAT_LINK = "https://t.me/hayatkhalvatspain"

BOT_USERNAME = "VitrinSpainBot"
PROJECT_NAME = "ویترین اسپانیا"

BACK_BUTTON = "🔙 بازگشت"
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

CATEGORY_OPTIONS = list(SUBCATEGORIES.keys())
