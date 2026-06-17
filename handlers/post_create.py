from telegram import ReplyKeyboardMarkup
from telegram import Update
from telegram.ext import ContextTypes

from database.db import save_post
from handlers.admin import send_post_to_admin


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
    ],
    resize_keyboard=True,
)


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()
    context.user_data["post_step"] = "category"

    await update.message.reply_text(
        "📂 دسته آگهی را انتخاب کنید:",
        reply_markup=CATEGORY_KEYBOARD,
    )


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if "post_step" not in context.user_data:
        return

    if not update.message:
        return

    text = update.message.text
    step = context.user_data["post_step"]

    if step == "category":

        context.user_data["category"] = text
        context.user_data["post_step"] = "name"

        await update.message.reply_text(
            "👤 نام نمایشی خود را وارد کنید:"
        )

        return

    if step == "name":

        context.user_data["display_name"] = text
        context.user_data["post_step"] = "city"

        await update.message.reply_text(
            "📍 شهر خود را وارد کنید:"
        )

        return

    if step == "city":

        context.user_data["city"] = text
        context.user_data["post_step"] = "content"

        await update.message.reply_text(
            "📝 متن آگهی را وارد کنید:"
        )

        return

    if step == "content":

        await update.message.reply_text(
            "مرحله 1"
        )

        username = update.effective_user.username

        if username:
            telegram_id = f"@{username}"
        else:
            telegram_id = "بدون یوزرنیم"

        post_id = 999

        await update.message.reply_text(
            "مرحله 2"
        )

        await send_post_to_admin(
            context=context,
            post_id=post_id,
            post_data={
                "category": context.user_data["category"],
                "city": context.user_data["city"],
                "display_name": context.user_data["display_name"],
                "telegram_id": telegram_id,
                "content": text,
            },
        )

        await update.message.reply_text(
            "مرحله 3"
        )

        await update.message.reply_text(
            f"✅ آگهی شما ثبت شد.\n\n"
            f"شماره آگهی: {post_id}\n\n"
            f"پس از تایید ادمین منتشر خواهد شد."
        )

        context.user_data.clear()

        return
