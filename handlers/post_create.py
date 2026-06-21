from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from config_v2 import BACK_BUTTON, CATEGORY_OPTIONS, HOME_BUTTON, SUBCATEGORIES
from database.db import (
    get_post,
    get_user_profile,
    mark_pending_post_for_resubmission,
    save_post,
    save_user_profile,
    soft_delete_post_by_owner,
)
from handlers.admin import send_post_to_admin
from handlers.common import list_keyboard, user_manage_keyboard
from handlers.start import MAIN_MENU


CONFIRM_PREVIEW = "✅ تایید و ارسال برای بررسی"
EDIT_PREVIEW_TEXT = "✏️ ویرایش متن آگهی"
DELETE_PREVIEW = "🗑️ حذف آگهی"

STEP_PROMPTS = {
    "category": "📂 دسته آگهی را انتخاب کنید:",
    "subcategory": "📂 زیردسته آگهی را انتخاب کنید:",
    "display_name": "👤 نام نمایشی خود را وارد کنید:",
    "city": "📍 شهر خود را وارد کنید:",
    "content": "📝 متن آگهی را وارد کنید:",
}

PREVIEW_KEYBOARD = list_keyboard(
    [
        CONFIRM_PREVIEW,
        EDIT_PREVIEW_TEXT,
        DELETE_PREVIEW,
    ],
    include_back=False,
)


def step_keyboard(context: ContextTypes.DEFAULT_TYPE, step: str):
    if step == "category":
        return list_keyboard(CATEGORY_OPTIONS)
    if step == "subcategory":
        category = context.user_data.get("category")
        return list_keyboard(SUBCATEGORIES.get(category, []))
    return list_keyboard([])


def build_preview_text(context: ContextTypes.DEFAULT_TYPE):
    return (
        "پیش‌نمایش آگهی شما:\n\n"
        f"📂 دسته: {context.user_data['category']}\n"
        f"📂 زیردسته: {context.user_data['subcategory']}\n\n"
        f"📝 متن آگهی:\n{context.user_data['content']}\n\n"
        f"📍 شهر: {context.user_data['city']}\n"
        f"👤 نام نمایشی: {context.user_data['display_name']}"
    )


async def send_step_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, step: str):
    await update.message.reply_text(
        STEP_PROMPTS[step],
        reply_markup=step_keyboard(context, step),
    )


async def send_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_step"] = "preview"
    await update.message.reply_text(
        build_preview_text(context),
        reply_markup=PREVIEW_KEYBOARD,
    )


async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "به منوی اصلی برگشتید.",
        reply_markup=MAIN_MENU,
    )


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user_id = update.effective_user.id
    profile = get_user_profile(user_id)

    if profile:
        display_name, city = profile
        context.user_data["display_name"] = display_name
        context.user_data["city"] = city
        step_order = ["category", "subcategory", "content"]
    else:
        step_order = ["category", "subcategory", "display_name", "city", "content"]

    context.user_data["step_order"] = step_order
    context.user_data["step_index"] = 0
    context.user_data["post_step"] = step_order[0]

    await send_step_prompt(update, context, step_order[0])


async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step_order = context.user_data.get("step_order", [])
    step_index = context.user_data.get("step_index", 0)

    if step_index <= 0:
        context.user_data.clear()
        await update.message.reply_text(
            "فرایند ثبت آگهی لغو شد.",
            reply_markup=MAIN_MENU,
        )
        return

    step_index -= 1
    previous_step = step_order[step_index]
    context.user_data["step_index"] = step_index
    context.user_data["post_step"] = previous_step
    await send_step_prompt(update, context, previous_step)


async def advance_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step_order = context.user_data["step_order"]
    step_index = context.user_data["step_index"] + 1
    context.user_data["step_index"] = step_index
    context.user_data["post_step"] = step_order[step_index]
    await send_step_prompt(update, context, step_order[step_index])


async def confirm_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    telegram_id = f"@{user.username}" if user.username else "بدون یوزرنیم"

    post_id = save_post(
        user_id=user.id,
        category=context.user_data["category"],
        subcategory=context.user_data["subcategory"],
        city=context.user_data["city"],
        display_name=context.user_data["display_name"],
        telegram_id=telegram_id,
        content=context.user_data["content"],
    )

    save_user_profile(
        user_id=user.id,
        display_name=context.user_data["display_name"],
        city=context.user_data["city"],
        username=user.username,
    )

    await send_post_to_admin(context=context, post_id=post_id)

    context.user_data.clear()
    await update.message.reply_text(
        "آگهی شما ثبت شد و پس از تایید ادمین منتشر می‌شود.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        "مدیریت آگهی:",
        reply_markup=user_manage_keyboard(post_id),
    )


async def handle_preview_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if text == HOME_BUTTON:
        await go_home(update, context)
        return

    if text == CONFIRM_PREVIEW:
        await confirm_preview(update, context)
        return

    if text == EDIT_PREVIEW_TEXT:
        context.user_data.pop("content", None)
        context.user_data["post_step"] = "content"
        await send_step_prompt(update, context, "content")
        return

    if text == DELETE_PREVIEW:
        context.user_data.clear()
        await update.message.reply_text(
            "آگهی حذف شد و چیزی ذخیره نشد.",
            reply_markup=MAIN_MENU,
        )
        return

    await update.message.reply_text(
        "لطفا یکی از گزینه‌های پیش‌نمایش را انتخاب کنید.",
        reply_markup=PREVIEW_KEYBOARD,
    )


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "post_step" not in context.user_data:
        return

    if not update.message:
        return

    text = update.message.text.strip()
    step = context.user_data["post_step"]

    if text == HOME_BUTTON:
        await go_home(update, context)
        return

    if step == "preview":
        await handle_preview_choice(update, context, text)
        return

    if text == BACK_BUTTON:
        await handle_back(update, context)
        return

    if step == "category":
        if text not in SUBCATEGORIES:
            await update.message.reply_text("لطفا یک دسته معتبر انتخاب کنید.")
            return

        context.user_data["category"] = text
        await advance_step(update, context)
        return

    if step == "subcategory":
        category = context.user_data.get("category")
        if text not in SUBCATEGORIES.get(category, []):
            await update.message.reply_text("لطفا یک زیردسته معتبر انتخاب کنید.")
            return

        context.user_data["subcategory"] = text
        await advance_step(update, context)
        return

    if step == "display_name":
        if len(text) < 2:
            await update.message.reply_text("نام نمایشی باید حداقل ۲ حرف باشد.")
            return

        context.user_data["display_name"] = text
        await advance_step(update, context)
        return

    if step == "city":
        if len(text) < 2:
            await update.message.reply_text("نام شهر باید حداقل ۲ حرف باشد.")
            return

        context.user_data["city"] = text
        await advance_step(update, context)
        return

    if step == "content":
        if len(text) < 5:
            await update.message.reply_text("متن آگهی خیلی کوتاه است.")
            return

        context.user_data["content"] = text
        await send_preview(update, context)


async def user_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, action, post_id_text = parts

    if action == "home":
        context.user_data.clear()
        await query.message.reply_text(
            "به منوی اصلی برگشتید.",
            reply_markup=MAIN_MENU,
        )
        return

    post_id = int(post_id_text)
    post = get_post(post_id)

    if not post:
        await query.edit_message_text("❌ آگهی پیدا نشد.")
        return

    if post["user_id"] != query.from_user.id:
        await query.edit_message_text("فقط صاحب آگهی می‌تواند این عملیات را انجام دهد.")
        return

    if action == "delete":
        if soft_delete_post_by_owner(post_id, query.from_user.id):
            await query.edit_message_text("🗑️ آگهی شما حذف شد.")
        else:
            await query.edit_message_text("حذف آگهی انجام نشد.")
        return

    if action == "edit":
        if post["status"] not in ("pending", "need_edit"):
            await query.edit_message_text("فقط آگهی‌های در انتظار بررسی یا نیازمند ویرایش قابل ویرایش هستند.")
            return

        if post["status"] == "pending":
            mark_pending_post_for_resubmission(post_id, query.from_user.id)

        context.user_data.clear()
        context.user_data["category"] = post["category"]
        context.user_data["subcategory"] = post.get("subcategory") or ""
        context.user_data["display_name"] = post.get("display_name") or ""
        context.user_data["city"] = post.get("city") or ""
        context.user_data["step_order"] = ["content"]
        context.user_data["step_index"] = 0
        context.user_data["post_step"] = "content"

        await query.edit_message_text(
            "✏️ لطفا متن اصلاح‌شده آگهی را ارسال کنید.\n"
            "بعد از ارسال متن، پیش‌نمایش را می‌بینید و می‌توانید برای بررسی ادمین تایید کنید."
        )
        await query.message.reply_text(
            "📝 متن آگهی را وارد کنید:",
            reply_markup=step_keyboard(context, "content"),
        )
