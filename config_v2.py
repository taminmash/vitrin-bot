import os


BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN تنظیم نشده است.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL تنظیم نشده است.")


ADMIN_ID = int(os.environ.get("ADMIN_ID", "8747305714"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003945260173"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "VitrinSpainBot")


POST_STATUS_PENDING = "pending"
POST_STATUS_NEEDS_EDIT = "needs_edit"
POST_STATUS_PUBLISHED = "published"
POST_STATUS_DELETED = "deleted"


STATUS_LABELS = {
    POST_STATUS_PENDING: "🟡 در انتظار تایید",
    POST_STATUS_NEEDS_EDIT: "📝 نیازمند ویرایش",
    POST_STATUS_PUBLISHED: "✅ منتشر شده",
    POST_STATUS_DELETED: "❌ حذف شده",
}


CATEGORIES = [
    "کار و درآمد",
    "خانه‌یابی",
    "خرید و فروش",
    "خدمات و ارتباطات",
    "سرمایه و وام",
    "خرید و فروش یورو",
    "تبلیغات ویژه",
]


SUBCATEGORIES = {
    "کار و درآمد": [
        "معرفی کارجو",
        "آگهی استخدام",
    ],
    "خانه‌یابی": [
        "خانه اشتراکی و هم‌خانه",
        "آگهی اجاره",
        "جستجوی اجاره",
        "آگهی فروش",
        "درخواست خرید",
    ],
    "خرید و فروش": [
        "خودرو",
        "موبایل و دیجیتال",
        "لوازم خانه",
        "کودک و نوزاد",
        "پوشاک",
        "تجهیزات کاری",
        "واگذاری رایگان",
        "سایر",
    ],
    "خدمات و ارتباطات": [
        "درمانی و پزشکی",
        "زیبایی و آرایشی",
        "رستوران و کافه",
        "فنی",
        "املاک",
        "مالی",
        "حقوقی و اداری",
        "مهاجرتی و توریستی",
        "بیمه",
        "خودرو",
        "دیجیتال، طراحی و گرافیک",
        "آموزشی",
        "نظافت",
        "پرستاری و نگهداری",
        "حمل اثاثیه",
        "حمل و نقل",
        "قفل‌سازی",
        "باغبانی",
        "عکاسی و فیلمبرداری",
        "آشپزی و کترینگ",
        "سایر",
    ],
    "سرمایه و وام": [
        "جذب سرمایه‌گذار",
        "آماده سرمایه‌گذاری",
    ],
    "خرید و فروش یورو": [
        "خرید یورو",
        "فروش یورو",
    ],
    "تبلیغات ویژه": [
        "پکیج تبلیغاتی",
        "همکاری تبلیغاتی",
    ],
}


BACK_BUTTON = "🔙 بازگشت"
