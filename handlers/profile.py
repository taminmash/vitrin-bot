from telegram import ReplyKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes


BACK_KEYBOARD = ReplyKeyboardMarkup(
    [
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
        ["📍 سایر شهرها"],
        ["🔙 بازگشت"],
    ],
    resize_keyboard=True,
)


async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["profile_step"] = "name"

    await update.message.reply_text(
        "👤 نام نمایشی خود را وارد کنید:",
        reply_markup=BACK_KEYBOARD,
    )


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "profile_step" not in context.user_data:
        return

    text = update.message.text
    step = context.user_data["profile_step"]

    if text == "🔙 بازگشت":

        if step == "name":

            context.user_data.clear()

            await update.message.reply_text(
                "به منوی اصلی برگشتید."
            )

            return

        if step == "city":

            context.user_data["profile_step"] = "name"

            await update.message.reply_text(
                "👤 نام نمایشی خود را وارد کنید:",
                reply_markup=BACK_KEYBOARD,
            )

            return

    if step == "name":

        context.user_data["display_name"] = text
        context.user_data["profile_step"] = "city"

        await update.message.reply_text(
            "📍 شهر خود را انتخاب کنید:",
            reply_markup=CITY_KEYBOARD,
        )

        return

    if step == "city":

        context.user_data["city"] = text

        await update.message.reply_text(
            f"✅ پروفایل ثبت شد.\n\n"
            f"👤 نام: {context.user_data['display_name']}\n"
            f"📍 شهر: {context.user_data['city']}"
        )

        context.user_data.clear()
