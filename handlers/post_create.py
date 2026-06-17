from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram import Update
from telegram.ext import ContextTypes
from database.db import (
    save_post,
    update_post_content,
    get_pending_edit_post,
    get_post,
    get_user_profile,
    save_user_profile,
)
from handlers.admin import send_post_to_admin

BACK_BUTTON = "🔙 بازگشت"

CATEGORY_OPTIONS = [
    "💼 کار و درآمد",
    "🏠 خانه و اجاره",
    "🛒 خرید و فروش",
    "🔧 خدمات",
    "🚚 ارسال بار",
    "💰 سرمایه گذاری",
    "💶 خرید و فروش یورو",
    "📢 آگهی ویژه",
]

CATEGORY_KEYBOARD = ReplyKeyboardMarkup(
    [[option] for option in CATEGORY_OPTIONS],
    resize_keyboard=True,
)

BACK_KEYBOARD = ReplyKeyboardMarkup(
    [[BACK_BUTTON]],
    resize_keyboard=True,
)

STEP_PROMPTS = {
    "category": ("📂 دسته آگهی را انتخاب کنید:", CATEGORY_KEYBOARD),
    "name": ("👤 نام نمایشی خود را وارد کنید:", BACK_KEYBOARD),
    "city": ("📍 شهر خود را وارد کنید:", BACK_KEYBOARD),
    "content": ("📝 متن آگهی را وارد کنید:", BACK_KEYBOARD),
}


async def send_step_prompt(update: Update, step: str):
    prompt_text, keyboard = STEP_PROMPTS[step]
    await update.message.reply_text(
        prompt_text,
        reply_markup=keyboard,
    )


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user_id = update.effective_user.id

    edit_post_id = get_pending_edit_post(user_id)

    if edit_post_id:
        old_post = get_post(edit_post_id)

        context.user_data["edit_post_id"] = edit_post_id
        context.user_data["category"] = old_post[2]
        context.user_data["city"] = old_post[3]
        context.user_data["display_name"] = old_post[4]

        context.user_data["step_order"] = ["content"]
        context.user_data["step_index"] = 0
        context.user_data["post_step"] = "content"

        await update.message.reply_text(
            "📝 لطفاً متن جدید آگهی را ارسال کنید:"
        )
        return

    profile = get_user_profile(user_id)

    if profile:
        display_name, city = profile
        context.user_data["display_name"] = display_name
        context.user_data["city"] = city
        context.user_data["step_order"] = ["category", "content"]
    else:
        context.user_data["step_order"] = ["category", "name", "city", "content"]

    context.user_data["step_index"] = 0
    context.user_data["post_step"] = context.user_data["step_order"][0]

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
    step_order = context.user_data.get("step_order", [])
    step_index = context.user_data.get("step_index", 0)

    if text == BACK_BUTTON:
        if step_index > 0:
            step_index -= 1
            context.user_data["step_index"] = step_index
            prev_step = step_order[step_index]
            context.user_data["post_step"] = prev_step
            await send_step_prompt(update, prev_step)
        else:
            await update.message.reply_text(
                "این ابتدای فرآیند ثبت آگهی است."
            )
        return

    if step == "category":
        context.user_data["category"] = text
        step_index += 1
        context.user_data["step_index"] = step_index
        next_step = step_order[step_index]
        context.user_data["post_step"] = next_step
        await send_step_prompt(update, next_step)
        return

    if step == "name":
        context.user_data["display_name"] = text
        step_index += 1
        context.user_data["step_index"] = step_index
        next_step = step_order[step_index]
        context.user_data["post_step"] = next_step
        await send_step_prompt(update, next_step)
        return

    if step == "city":
        context.user_data["city"] = text
        step_index += 1
        context.user_data["step_index"] = step_index
        next_step = step_order[step_index]
        context.user_data["post_step"] = next_step
        await send_step_prompt(update, next_step)
        return

    if step == "content":
        await update.message.reply_text("مرحله 1")

        username = update.effective_user.username
        if username:
            telegram_id = f"@{username}"
        else:
            telegram_id = "بدون یوزرنیم"

        edit_post_id = context.user_data.get("edit_post_id")

        if edit_post_id:
            post_id = edit_post_id

            update_post_content(
                post_id=post_id,
                content=text,
            )

            confirmation_text = (
                "✅ آگهی ویرایش‌شده شما ثبت شد.\n\n"
                "پس از تایید ادمین در کانال منتشر خواهد شد."
            )
        else:
            user_id = update.effective_user.id

            post_id = save_post(
                user_id=user_id,
                category=context.user_data["category"],
                city=context.user_data["city"],
                display_name=context.user_data["display_name"],
                telegram_id=telegram_id,
                content=text,
            )

            save_user_profile(
                user_id=user_id,
                display_name=context.user_data["display_name"],
                city=context.user_data["city"],
                username=username,
            )

            confirmation_text = (
                f"✅ آگهی شما ثبت شد.\n\n"
                f"شماره آگهی: {post_id}\n\n"
                f"پس از تایید ادمین منتشر خواهد شد."
            )

        await update.message.reply_text("مرحله 2")

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

        await update.message.reply_text("مرحله 3")

        await update.message.reply_text(
            confirmation_text,
            reply_markup=ReplyKeyboardRemove(),
        )

        context.user_data.clear()
        return
