from telegram import ReplyKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes


CATEGORY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💼 کار و درآمد"],
        ["🏠 خانه و اجاره"],
        ["🛒 خرید و فروش"],
        ["🔧 خدمات"],
        ["💰 سرمایه گذاری"],
        ["💶 خرید و فروش یورو"],
        ["📢 آگهی ویژه"],
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
        ["📍 سایر شهرها"],
    ],
    resize_keyboard=True,
)


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["post_step"] = "category"

    await update.message.reply_text(
        "دسته آگهی را انتخاب کنید:",
        reply_markup=CATEGORY_KEYBOARD,
    )


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "post_step" not in context.user_data:
        return

    text = update.message.text
    step = context.user_data["post_step"]

    if step == "category":

        context.user_data["post_category"] = text
        context.user_data["post_step"] = "city"

        await update.message.reply_text(
            "شهر را انتخاب کنید:",
            reply_markup=CITY_KEYBOARD,
        )

        return

    if step == "city":

        context.user_data["post_city"] = text
        context.user_data["post_step"] = "name"

        await update.message.reply_text(
            "نام نمایشی خود را وارد کنید:"
        )

        return

    if step == "name":

        context.user_data["post_name"] = text
        context.user_data["post_step"] = "telegram"

        await update.message.reply_text(
            "آیدی تلگرام خود را وارد کنید:"
        )

        return

    if step == "telegram":

        context.user_data["post_telegram"] = text
        context.user_data["post_step"] = "content"

        await update.message.reply_text(
            "متن آگهی را ارسال کنید:"
        )

        return

    if step == "content":

        context.user_data["post_content"] = text

        preview = f"""
📋 پیش نمایش آگهی

دسته:
{context.user_data['post_category']}

شهر:
{context.user_data['post_city']}

نام:
{context.user_data['post_name']}

تلگرام:
{context.user_data['post_telegram']}

متن:

{context.user_data['post_content']}
"""

        await update.message.reply_text(preview)

        context.user_data.clear()
