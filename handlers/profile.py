from telegram import ReplyKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes

from handlers.start import MAIN_MENU


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


async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()
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

    # بازگشت
    if text == "🔙 بازگشت":

        if step == "name":

            context.user_data.clear()

            await update.message.reply_text(
                "🏠 به منوی اصلی برگشتید.",
                reply_markup=MAIN_MENU,
            )

            return

        if step == "city":

            context.user_data["profile_step"] = "name"

            await update.message.reply_text(
                "👤 نام نمایشی خود را وارد کنید:",
                reply_markup=BACK_KEYBOARD,
            )

            return

        if step == "other_city":

            context.user_data["profile_step"] = "city"

            await update.message.reply_text(
                "📍 شهر خود را انتخاب کنید:",
                reply_markup=CITY_KEYBOARD,
            )

            return

    # نام نمایشی
    if step == "name":

        if len(text.strip()) < 2:

            await update.message.reply_text(
                "نام نمایشی حداقل باید ۲ حرف باشد."
            )

            return

        context.user_data["display_name"] = text.strip()
        context.user_data["profile_step"] = "city"

        await update.message.reply_text(
            "📍 شهر خود را انتخاب کنید:",
            reply_markup=CITY_KEYBOARD,
        )

        return

    # انتخاب شهر
    if step == "city":

        if text == "📍 سایر شهرها":

            context.user_data["profile_step"] = "other_city"

            await update.message.reply_text(
                "📍 نام شهر را وارد کنید:",
                reply_markup=BACK_KEYBOARD,
            )

            return

        context.user_data["city"] = text.replace("📍 ", "")

        await update.message.reply_text(
            f"✅ پروفایل ثبت شد.\n\n"
            f"👤 نام: {context.user_data['display_name']}\n"
            f"📍 شهر: {context.user_data['city']}",
            reply_markup=MAIN_MENU,
        )

        context.user_data.clear()

        return

    # سایر شهرها
    if step == "other_city":

        context.user_data["city"] = text.strip()

        await update.message.reply_text(
            f"✅ پروفایل ثبت شد.\n\n"
            f"👤 نام: {context.user_data['display_name']}\n"
            f"📍 شهر: {context.user_data['city']}",
            reply_markup=MAIN_MENU,
        )

        context.user_data.clear()
