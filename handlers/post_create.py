from telegram import ReplyKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes


BACK_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

CATEGORY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💼 کار و درآمد"],
        ["🏠 خانه و اجاره"],
        ["🛒 خرید و فروش"],
        ["🔧 خدمات"],
        ["🚚 ارسال بار"],
        ["💰 سرمایه گذاری"],
        ["💶 خرید و فروش یورو"],
        ["📢 آگهی ویژه"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

CITY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📍 مادرید", "📍 بارسلونا"],
        ["📍 والنسیا", "📍 مالاگا"],
        ["📍 سویا", "📍 آلیکانته"],
        ["📍 مورسیا", "📍 بیلبائو"],
        ["📍 ساراگوسا", "📍 باداخوس"],
        ["📍 وایادولید", "📍 سالامانکا"],
        ["📍 گرانادا", "📍 کوردوبا"],
        ["📍 کادیز", "📍 ماربیا"],
        ["📍 تنریف", "📍 لاس پالماس"],
        ["📍 اوویدو", "📍 خیخون"],
        ["📍 پامپلونا", "📍 لئون"],
        ["📍 تولدو", "📍 گوادالاخارا"],
        ["📍 سایر شهرها"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)

CONFIRM_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✅ تایید و ارسال"],
        ["❌ لغو"],
    ],
    resize_keyboard=True,
)


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["post_step"] = "category"

    await update.message.reply_text(
        "📂 دسته آگهی را انتخاب کنید:",
        reply_markup=CATEGORY_KEYBOARD,
    )


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "post_step" not in context.user_data:
        return

    text = update.message.text
    step = context.user_data["post_step"]

    # بازگشت
    if text == "🔙 بازگشت":

        if step == "category":

            context.user_data.clear()

            await update.message.reply_text(
                "به منوی اصلی برگشتید."
            )

            return

        if step == "city":

            context.user_data["post_step"] = "category"

            await update.message.reply_text(
                "📂 دسته آگهی را انتخاب کنید:",
                reply_markup=CATEGORY_KEYBOARD,
            )

            return

        if step == "other_city":

            context.user_data["post_step"] = "city"

            await update.message.reply_text(
                "📍 شهر را انتخاب کنید:",
                reply_markup=CITY_KEYBOARD,
            )

            return

        if step == "name":

            context.user_data["post_step"] = "city"

            await update.message.reply_text(
                "📍 شهر را انتخاب کنید:",
                reply_markup=CITY_KEYBOARD,
            )

            return

        if step == "telegram":

            context.user_data["post_step"] = "name"

            await update.message.reply_text(
                "👤 نام نمایشی خود را وارد کنید:",
                reply_markup=BACK_KEYBOARD,
            )

            return

        if step == "content":

            context.user_data["post_step"] = "telegram"

            await update.message.reply_text(
                "📨 آیدی تلگرام خود را وارد کنید:",
                reply_markup=BACK_KEYBOARD,
            )

            return

    # دسته
    if step == "category":

        context.user_data["post_category"] = text
        context.user_data["post_step"] = "city"

        await update.message.reply_text(
            "📍 شهر را انتخاب کنید:",
            reply_markup=CITY_KEYBOARD,
        )

        return

    # شهر
    if step == "city":

        if text == "📍 سایر شهرها":

            context.user_data["post_step"] = "other_city"

            await update.message.reply_text(
                "📍 نام شهر را وارد کنید:",
                reply_markup=BACK_KEYBOARD,
            )

            return

        context.user_data["post_city"] = text.replace("📍 ", "")
        context.user_data["post_step"] = "name"

        await update.message.reply_text(
            "👤 نام نمایشی خود را وارد کنید:",
            reply_markup=BACK_KEYBOARD,
        )

        return

    # سایر شهرها
    if step == "other_city":

        context.user_data["post_city"] = text
        context.user_data["post_step"] = "name"

        await update.message.reply_text(
            "👤 نام نمایشی خود را وارد کنید:",
            reply_markup=BACK_KEYBOARD,
        )

        return

    # نام
    if step == "name":

        context.user_data["post_name"] = text
        context.user_data["post_step"] = "telegram"

        await update.message.reply_text(
            "📨 آیدی تلگرام خود را وارد کنید:",
            reply_markup=BACK_KEYBOARD,
        )

        return

    # تلگرام
    if step == "telegram":

        context.user_data["post_telegram"] = text
        context.user_data["post_step"] = "content"

        await update.message.reply_text(
            "📝 متن آگهی را ارسال کنید:",
            reply_markup=BACK_KEYBOARD,
        )

        return

    # متن آگهی
    if step == "content":

        context.user_data["post_content"] = text
        context.user_data["post_step"] = "confirm"

        preview = f"""
📋 پیش نمایش آگهی

📂 دسته:
{context.user_data['post_category']}

📍 شهر:
{context.user_data['post_city']}

👤 نام:
{context.user_data['post_name']}

📨 تلگرام:
{context.user_data['post_telegram']}

📝 متن:

{context.user_data['post_content']}
"""

        await update.message.reply_text(
            preview,
            reply_markup=CONFIRM_KEYBOARD,
        )

        return

    # تایید
    if step == "confirm":

        if text == "✅ تایید و ارسال":

            await update.message.reply_text(
                "✅ آگهی شما ثبت شد و پس از بررسی منتشر خواهد شد."
            )

            context.user_data.clear()

            return

        if text == "❌ لغو":

            await update.message.reply_text(
                "❌ ثبت آگهی لغو شد."
            )

            context.user_data.clear()

            return
