import re

from telegram import Update
from telegram.ext import ContextTypes

from config_v2 import ADMIN_IDS, BACK_BUTTON, CATEGORY_OPTIONS, HOME_BUTTON, SUBCATEGORIES
from database.db import (
    get_post,
    get_user_profile,
    mark_pending_post_for_resubmission,
    save_post,
    save_user_profile,
    soft_delete_post_by_owner,
)
from handlers.admin import send_post_to_admin
from handlers.common import list_keyboard
from handlers.start import MAIN_MENU


CONFIRM_PREVIEW = "✅ تایید و ارسال آگهی"
EDIT_PREVIEW_TEXT = "✏️ ویرایش آگهی"
DELETE_PREVIEW = "🗑️ حذف آگهی"
CONTENT_RESTRICTION_WARNING = "⚠️ ارسال لینک، تصویر و شماره تلفن مجاز نمی‌باشد."
TEXT_RESTRICTION_ERROR = (
    "❌ ارسال لینک، آیدی تلگرام، تصویر، ویدیو یا شماره تلفن مجاز نمی‌باشد.\n\n"
    "لطفاً متن را بدون اطلاعات تماس ارسال کنید."
)
MEDIA_RESTRICTION_ERROR = (
    "❌ ارسال تصویر یا ویدیو برای کاربران عادی مجاز نیست.\n\n"
    "لطفاً متن پیام را بدون تصویر یا ویدیو ارسال کنید."
)
URL_PATTERN = re.compile(
    r"(?:https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE,
)
TELEGRAM_HANDLE_PATTERN = re.compile(r"(?<!\w)@[A-Za-z0-9_]{5,32}\b")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+|00)?\d[\d\s().-]{7,}\d(?!\w)")
HAYAT_CATEGORIES = [
    "🕊️ پیام ناشناس",
    "📖 دورهمی و تجربه",
    "🧠 دانستنی‌ها و خبرها",
]
HAYAT_AUTHOR_ANONYMOUS = "ناشناس"
HAYAT_AUTHOR_PROFILE = "نام نمایشی من"
HAYAT_AUTHOR_CUSTOM = "نام دلخواه"
HAYAT_AUTHOR_OPTIONS = [
    HAYAT_AUTHOR_ANONYMOUS,
    HAYAT_AUTHOR_PROFILE,
    HAYAT_AUTHOR_CUSTOM,
]
HAYAT_BLOCKED_AUTHOR_PARTS = (
    "@",
    "t.me/",
    "telegram.me/",
    "http://",
    "https://",
)

STEP_PROMPTS = {
    "category": "📂 دسته آگهی را انتخاب کنید:",
    "subcategory": "📂 زیردسته آگهی را انتخاب کنید:",
    "display_name": "👤 نام نمایشی خود را وارد کنید:",
    "city": "📍 شهر خود را وارد کنید:",
    "content": f"📝 متن آگهی را وارد کنید:\n\n{CONTENT_RESTRICTION_WARNING}",
    "hayat_category": "📂 دسته پیام حیاط خلوت را انتخاب کنید:",
    "hayat_author_choice": "می‌خواهید نام نویسنده نمایش داده شود؟",
    "hayat_writer_name": "✍️ نام نویسنده را وارد کنید:",
    "hayat_content": f"📝 متن پیام را وارد کنید:\n\n{CONTENT_RESTRICTION_WARNING}",
}

PREVIEW_KEYBOARD = list_keyboard(
    [
        CONFIRM_PREVIEW,
        EDIT_PREVIEW_TEXT,
        DELETE_PREVIEW,
    ],
    include_back=False,
    include_home=True,
)


def step_keyboard(context: ContextTypes.DEFAULT_TYPE, step: str):
    if step == "category":
        return list_keyboard(CATEGORY_OPTIONS)
    if step == "subcategory":
        category = context.user_data.get("category")
        return list_keyboard(SUBCATEGORIES.get(category, []))
    if step == "hayat_category":
        return list_keyboard(HAYAT_CATEGORIES)
    if step == "hayat_author_choice":
        return list_keyboard(HAYAT_AUTHOR_OPTIONS)
    return list_keyboard([])


def build_preview_text(context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("post_type") == "hayat":
        return (
            "پیش‌نمایش پیام حیاط خلوت:\n\n"
            f"📂 دسته: {context.user_data['category']}\n\n"
            f"متن پیام:\n{context.user_data['content']}\n\n"
            f"✍️ نویسنده: {context.user_data['display_name']}"
        )

    return (
        "پیش‌نمایش آگهی شما:\n\n"
        f"📂 دسته: {context.user_data['category']}\n"
        f"📂 زیردسته: {context.user_data['subcategory']}\n\n"
        f"📝 متن آگهی:\n{context.user_data['content']}\n\n"
        f"📍 شهر: {context.user_data['city']}\n"
        f"👤 نام نمایشی: {context.user_data['display_name']}"
    )


def is_safe_hayat_writer_name(text: str):
    lowered = text.lower()
    return not any(part in lowered for part in HAYAT_BLOCKED_AUTHOR_PARTS)


def safe_hayat_writer_name(text: str):
    text = (text or "").strip()
    if len(text) < 2 or not is_safe_hayat_writer_name(text):
        return HAYAT_AUTHOR_ANONYMOUS
    return text


def remove_next_hayat_writer_step(context: ContextTypes.DEFAULT_TYPE):
    step_order = context.user_data["step_order"]
    next_index = context.user_data["step_index"] + 1
    if next_index < len(step_order) and step_order[next_index] == "hayat_writer_name":
        step_order.pop(next_index)


def is_admin_user(update: Update):
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def has_phone_like_number(text: str):
    for match in PHONE_PATTERN.finditer(text):
        candidate = match.group()
        digits = re.sub(r"\D", "", candidate)
        if len(digits) < 9:
            continue
        if candidate.strip().startswith(("+", "00")):
            return True
        if len(digits) >= 9:
            return True
    return False


def has_restricted_text_content(text: str):
    return bool(
        URL_PATTERN.search(text)
        or TELEGRAM_HANDLE_PATTERN.search(text)
        or has_phone_like_number(text)
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


async def start_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    post_type: str = "vitrin",
):
    context.user_data.clear()
    context.user_data["post_type"] = post_type

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


async def start_hayat_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["post_type"] = "hayat"
    context.user_data["step_order"] = [
        "hayat_category",
        "hayat_author_choice",
        "hayat_content",
    ]
    context.user_data["step_index"] = 0
    context.user_data["post_step"] = "hayat_category"

    await send_step_prompt(update, context, "hayat_category")


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
    post_type = context.user_data.get("post_type", "vitrin")

    if post_type == "hayat":
        post_id = save_post(
            user_id=user.id,
            category=context.user_data["category"],
            subcategory=None,
            city=None,
            display_name=context.user_data["display_name"],
            telegram_id=None,
            content=context.user_data["content"],
            post_type="hayat",
        )

        await send_post_to_admin(context=context, post_id=post_id)

        context.user_data.clear()
        await update.message.reply_text(
            "پیام شما ثبت شد و پس از تایید ادمین منتشر می‌شود.",
            reply_markup=MAIN_MENU,
        )
        return

    telegram_id = f"@{user.username}" if user.username else "بدون یوزرنیم"

    post_id = save_post(
        user_id=user.id,
        category=context.user_data["category"],
        subcategory=context.user_data["subcategory"],
        city=context.user_data["city"],
        display_name=context.user_data["display_name"],
        telegram_id=telegram_id,
        content=context.user_data["content"],
        post_type=context.user_data.get("post_type", "vitrin"),
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
        reply_markup=MAIN_MENU,
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
        content_step = "hayat_content" if context.user_data.get("post_type") == "hayat" else "content"
        context.user_data["post_step"] = content_step
        await send_step_prompt(update, context, content_step)
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

    step = context.user_data["post_step"]
    has_restricted_media = bool(update.message.photo or update.message.video)

    if has_restricted_media:
        if not is_admin_user(update):
            await update.message.reply_text(MEDIA_RESTRICTION_ERROR)
        return

    if not update.message.text:
        return

    text = update.message.text.strip()

    if text == HOME_BUTTON:
        await go_home(update, context)
        return

    if step == "preview":
        await handle_preview_choice(update, context, text)
        return

    if text == BACK_BUTTON:
        await handle_back(update, context)
        return

    if step == "hayat_category":
        if text not in HAYAT_CATEGORIES:
            await update.message.reply_text("لطفا یک دسته معتبر برای حیاط خلوت انتخاب کنید.")
            return

        context.user_data["category"] = text
        await advance_step(update, context)
        return

    if step == "hayat_author_choice":
        if text not in HAYAT_AUTHOR_OPTIONS:
            await update.message.reply_text("لطفا یکی از گزینه‌های نام نویسنده را انتخاب کنید.")
            return

        if text == HAYAT_AUTHOR_ANONYMOUS:
            remove_next_hayat_writer_step(context)
            context.user_data["display_name"] = HAYAT_AUTHOR_ANONYMOUS
            await advance_step(update, context)
            return

        if text == HAYAT_AUTHOR_PROFILE:
            remove_next_hayat_writer_step(context)
            profile = get_user_profile(update.effective_user.id)
            if profile:
                context.user_data["display_name"] = safe_hayat_writer_name(profile[0])
            else:
                context.user_data["display_name"] = safe_hayat_writer_name(update.effective_user.full_name)
            await advance_step(update, context)
            return

        step_order = context.user_data["step_order"]
        next_index = context.user_data["step_index"] + 1
        if next_index >= len(step_order) or step_order[next_index] != "hayat_writer_name":
            step_order.insert(next_index, "hayat_writer_name")
        await advance_step(update, context)
        return

    if step == "hayat_writer_name":
        if len(text) < 2:
            await update.message.reply_text("نام نویسنده باید حداقل ۲ حرف باشد.")
            return
        if not is_safe_hayat_writer_name(text):
            await update.message.reply_text("نام نویسنده نباید شامل یوزرنیم، لینک یا نشانی تلگرام باشد.")
            return

        context.user_data["display_name"] = text
        await advance_step(update, context)
        return

    if step == "hayat_content":
        if not is_admin_user(update) and has_restricted_text_content(text):
            await update.message.reply_text(TEXT_RESTRICTION_ERROR)
            return

        if len(text) < 5:
            await update.message.reply_text("متن پیام خیلی کوتاه است.")
            return

        context.user_data["content"] = text
        await send_preview(update, context)
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
        if not is_admin_user(update) and has_restricted_text_content(text):
            await update.message.reply_text(TEXT_RESTRICTION_ERROR)
            return

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
        item_label = "پیام" if post.get("post_type") == "hayat" else "آگهی"
        if soft_delete_post_by_owner(post_id, query.from_user.id):
            await query.edit_message_text(f"🗑️ {item_label} شما حذف شد.")
        else:
            await query.edit_message_text(f"حذف {item_label} انجام نشد.")
        return

    if action == "edit":
        if post["status"] not in ("pending", "need_edit"):
            item_label = "پیام" if post.get("post_type") == "hayat" else "آگهی"
            await query.edit_message_text(f"فقط {item_label}های در انتظار بررسی یا نیازمند ویرایش قابل ویرایش هستند.")
            return

        if post["status"] == "pending":
            mark_pending_post_for_resubmission(post_id, query.from_user.id)

        context.user_data.clear()
        context.user_data["category"] = post["category"]
        context.user_data["subcategory"] = post.get("subcategory") or ""
        context.user_data["display_name"] = post.get("display_name") or ""
        context.user_data["city"] = post.get("city") or ""
        context.user_data["post_type"] = post.get("post_type") or "vitrin"
        is_hayat = context.user_data["post_type"] == "hayat"
        content_step = "hayat_content" if is_hayat else "content"
        context.user_data["step_order"] = [content_step]
        context.user_data["step_index"] = 0
        context.user_data["post_step"] = content_step

        item_label = "پیام" if is_hayat else "آگهی"
        await query.edit_message_text(
            f"✏️ لطفا متن اصلاح‌شده {item_label} را ارسال کنید.\n"
            "بعد از ارسال متن، پیش‌نمایش را می‌بینید و می‌توانید برای بررسی ادمین تایید کنید."
        )
        await query.message.reply_text(
            STEP_PROMPTS[content_step],
            reply_markup=step_keyboard(context, content_step),
        )
