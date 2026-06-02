# ===================================================
# فایل تنظیمات بات
# ===================================================
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8931837221:AAF0riuaFkWUtxLisszk25SP3yfS-PeZ6wk")
ADMIN_ID = 41792255

# کانال‌ها
CHANNEL_VITRIN = -1003945260173
CHANNEL_HAYAT = -1003854428039

# کدام کتگوری به کدام کانال میره
CATEGORY_CHANNELS = {
    "🌿 حیاط خلوت اسپانیا": CHANNEL_HAYAT,
}
DEFAULT_CHANNEL = CHANNEL_VITRIN

CATEGORIES = {
    "💼 کار و درآمد": [
        ("👤 معرفی کارجو", "sub_work_jobseeker"),
        ("📋 آگهی استخدام", "sub_work_hiring"),
    ],
    "🏠 خانه‌یابی": [
        ("🏘 خانه اشتراکی و همخانه", "sub_house_shared"),
        ("🏠 آگهی اجاره", "sub_house_rent"),
        ("🔍 جستجوی اجاره", "sub_house_search"),
        ("🏡 آگهی فروش", "sub_house_sell"),
        ("🔑 درخواست خرید", "sub_house_buy"),
    ],
    "🛒 خرید و فروش": [
        ("🚗 خودرو", "sub_shop_car"),
        ("📱 موبایل و دیجیتال", "sub_shop_mobile"),
        ("🏠 لوازم خانه", "sub_shop_home"),
        ("👶 کودک و نوزاد", "sub_shop_baby"),
        ("👕 پوشاک", "sub_shop_clothes"),
        ("🧰 تجهیزات کاری", "sub_shop_tools"),
        ("🐶 حیوانات", "sub_shop_pets"),
        ("🎁 واگذاری رایگان", "sub_shop_free"),
        ("📦 سایر", "sub_shop_other"),
    ],
    "🔧 خدمات و ارتباطات": [
        ("🩺 خدمات درمانی و پزشکی", "sub_srv_medical"),
        ("💇 خدمات زیبایی و آرایشی", "sub_srv_beauty"),
        ("🍽 خدمات رستوران و کافه", "sub_srv_restaurant"),
        ("🛠 خدمات فنی", "sub_srv_technical"),
        ("🏘 خدمات املاک", "sub_srv_realestate"),
        ("💳 خدمات مالی", "sub_srv_finance"),
        ("⚖️ خدمات حقوقی و اداری", "sub_srv_legal"),
        ("✈️ خدمات مهاجرتی و توریستی", "sub_srv_immigration"),
        ("🛡 خدمات بیمه", "sub_srv_insurance"),
        ("🚙 خدمات خودرو", "sub_srv_car"),
        ("💻 خدمات دیجیتال، طراحی و گرافیک", "sub_srv_digital"),
        ("📚 خدمات آموزشی", "sub_srv_education"),
        ("🧹 خدمات نظافت", "sub_srv_cleaning"),
        ("👨‍⚕️ خدمات پرستاری، نگهداری کودک و سالمند", "sub_srv_care"),
        ("🚛 خدمات حمل اثاثیه", "sub_srv_moving"),
        ("🚌 خدمات حمل و نقل", "sub_srv_transport"),
        ("🗝 خدمات قفل‌سازی", "sub_srv_locksmith"),
        ("🌱 خدمات باغبانی", "sub_srv_garden"),
        ("📸 خدمات عکاسی و فیلمبرداری", "sub_srv_photo"),
        ("🍳 خدمات آشپزی و کترینگ", "sub_srv_catering"),
        ("📋 سایر موارد", "sub_srv_other"),
    ],
    "💰 سرمایه و وام": [
        ("💰 جذب سرمایه‌گذار", "sub_inv_attract"),
        ("💸 آماده سرمایه‌گذاری", "sub_inv_ready"),
    ],
    "🌿 حیاط خلوت اسپانیا": [
        ("💬 پیام ناشناس", "sub_hayat_anon"),
        ("🧭 تجربه‌ها", "sub_hayat_exp"),
        ("🎉 دورهمی", "sub_hayat_event"),
    ],
    "📢 تبلیغات ویژه": [
        ("📦 پکیج‌های تبلیغاتی (به زودی)", "sub_ads_packages"),
    ],
    "💬 پشتیبانی 💛💜": [
        ("💬 پشتیبان فنی 💛💜", "sub_support_main"),
    ],
}

# نگاشت از callback_data به نام نمایشی
SUBCAT_LABELS = {}
for cat, subs in CATEGORIES.items():
    for label, code in subs:
        SUBCAT_LABELS[code] = label

# زیربخش‌های مشترک حیاط خلوت
HAYAT_SUBCATS = [
    "🛂 مهاجرت و اقامت",
    "🏥 بیمه و درمان",
    "💳 مالیات و حسابداری",
    "🩺 پزشک و دارو",
    "🏫 مدرسه و تحصیل",
    "🚗 خودرو و گواهینامه",
    "🏠 خانه و اجاره",
    "💼 کار و بازار کار",
    "🏦 بانک و امور مالی",
    "📦 سایر",
]

COMING_SOON_SUBCATS = [
    "sub_ads_packages",
]

# زیربخش‌های حیاط خلوت
HAYAT_MAIN_SUBCATS = [
    "sub_hayat_anon",
    "sub_hayat_exp",
    "sub_hayat_event",
]

# همه زیربخش‌های حیاط خلوت ناشناس هستن
ANONYMOUS_SUBCATS = [
    "sub_hayat_anon",
    "sub_hayat_exp",
    "sub_hayat_event",
]

# زیربخش‌هایی که به ادمین میرن نه کانال
SUPPORT_SUBCATS = [
    "sub_support_main",
]
