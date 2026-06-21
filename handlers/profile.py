from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_user_profile
from handlers.common import home_keyboard


async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    profile = get_user_profile(update.effective_user.id)
    if not profile:
        await update.message.reply_text(
            "پروفایل شما هنوز ثبت نشده است.\n"
            "برای ساخت پروفایل، از «ثبت آگهی در ویترین» استفاده کنید.",
            reply_markup=home_keyboard(),
        )
        return

    display_name, city = profile
    await update.message.reply_text(
        "👤 پروفایل من\n\n"
        f"نام نمایشی: {display_name}\n"
        f"شهر: {city}\n\n"
        "ویرایش پروفایل در نسخه MVP غیرفعال است.",
        reply_markup=home_keyboard(),
    )


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return
