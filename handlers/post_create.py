import re

from telegram import Update
from telegram.ext import ContextTypes

from config_v2 import (
    ADMIN_IDS,
    BACK_BUTTON,
    CATEGORY_OPTIONS,
    CHANNEL_HAYAT_LINK,
    CHANNEL_HAYAT_USERNAME,
    CHANNEL_VITRIN_LINK,
    CHANNEL_VITRIN_USERNAME,
    HOME_BUTTON,
)
from database.db import (
    archive_content,
    create_comment,
    create_content,
    create_report,
    get_content,
    get_or_create_user,
    list_approved_comments,
    save_reaction,
    update_content,
    update_draft,
)
from handlers.admin import send_comment_to_admin, submit_content_to_admin
from handlers.common import draft_actions_keyboard, list_keyboard, preview_keyboard, content_preview_text
from handlers.start import MAIN_MENU


SKIP_PRICE = "بدون قیمت"
SKIP_MEDIA = "بدون عکس/ویدیو"
SKIP_CITY = "بدون شهر"
CONFIRM_HAYAT = "تایید پیام"
EDIT_HAYAT = "ویرایش پیام"
ARCHIVE_HAYAT = "آرشیو پیام"
CONTENT_RESTRICTION_WARNING = "⚠️ ارسال لینک و شماره تلفن در متن مجاز نمی‌باشد."
TEXT_RESTRICTION_ERROR = (
    "❌ ارسال لینک، آیدی تلگرام یا شماره تلفن مجاز نمی‌باشد.\n\n"
    "لطفاً متن را بدون اطلاعات تماس ارسال کنید."
)
URL_PATTERN = re.compile(r"(?:https?://|www\.|t\.me/|telegram\.me/)", re.IGNORECASE)
TELEGRAM_HANDLE_PATTERN = re.compile(r"(?<!\w)@[A-Za-z0-9_]{5,32}\b")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+|00)?\d[\d\s().-]{7,}\d(?!\w)")


STEP_PROMPTS = {
    "vitrin_category": "📂 دسته آگهی را انتخاب کنید:",
    "vitrin_city": "📍 شهر آگهی را وارد کنید:",
    "vitrin_title": "🏷 عنوان آگهی را وارد کنید:",
    "vitrin_description": f"📝 توضیحات آگهی را وارد کنید:\n\n{CONTENT_RESTRICTION_WARNING}",
    "vitrin_price": "💶 قیمت را وارد کنید یا «بدون قیمت» را بزنید:",
    "vitrin_media": "🖼 عکس یا ویدیو را ارسال کنید یا «بدون عکس/ویدیو» را بزنید:",
    "hayat_city": "📍 شهر را وارد کنید یا «بدون شهر» را بزنید:",
    "hayat_message": f"📝 متن پیام ناشناس را وارد کنید:\n\n{CONTENT_RESTRICTION_WARNING}",
}


def is_admin_user(update: Update):
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)


def has_phone_like_number(text: str):
    for match in PHONE_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) >= 9:
            return True
    return False


def has_restricted_text_content(text: str):
    return bool(
        URL_PATTERN.search(text)
        or TELEGRAM_HANDLE_PATTERN.search(text)
        or has_phone_like_number(text)
    )


def step_keyboard(step):
    if step == "vitrin_category":
        return list_keyboard(CATEGORY_OPTIONS)
    if step == "vitrin_price":
        return list_keyboard([SKIP_PRICE])
    if step == "vitrin_media":
        return list_keyboard([SKIP_MEDIA])
    if step == "hayat_city":
        return list_keyboard([SKIP_CITY])
    return list_keyboard([])


def next_step(step):
    order = [
        "vitrin_category",
        "vitrin_city",
        "vitrin_title",
        "vitrin_description",
        "vitrin_price",
        "vitrin_media",
    ]
    if step in order:
        index = order.index(step)
        return order[index + 1] if index + 1 < len(order) else "preview"

    hayat_order = ["hayat_city", "hayat_message", "hayat_confirm"]
    index = hayat_order.index(step)
    return hayat_order[index + 1] if index + 1 < len(hayat_order) else "preview"


def missing_required_fields(content):
    if content["content_type"] == "hayat":
        required = [("description", "متن پیام")]
    else:
        required = [
            ("category", "دسته"),
            ("city", "شهر"),
            ("title", "عنوان"),
            ("description", "توضیحات"),
        ]
    return [label for key, label in required if not content.get(key)]


async def ensure_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type):
    if is_admin_user(update):
        return True

    channel = CHANNEL_HAYAT_USERNAME if content_type == "hayat" else CHANNEL_VITRIN_USERNAME
    link = CHANNEL_HAYAT_LINK if content_type == "hayat" else CHANNEL_VITRIN_LINK
    try:
        member = await context.bot.get_chat_member(channel, update.effective_user.id)
        if member.status in ("member", "administrator", "creator"):
            return True
    except Exception:
        pass

    await update.message.reply_text(
        "برای ارسال محتوا ابتدا عضو کانال مربوطه شوید:\n\n"
        f"{link}\n\n"
        "بعد از عضویت، دوباره از منوی اصلی شروع کنید.",
        reply_markup=MAIN_MENU,
        disable_web_page_preview=True,
    )
    return False


async def send_step_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, step):
    context.user_data["post_step"] = step
    update_draft(context.user_data["content_id"], current_step=step)
    await update.message.reply_text(STEP_PROMPTS[step], reply_markup=step_keyboard(step))


async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE, post_type="vitrin"):
    if not await ensure_channel_membership(update, context, "vitrin"):
        return

    get_or_create_user(update.effective_user)
    content = create_content(update.effective_user.id, "vitrin")
    context.user_data.clear()
    context.user_data["flow"] = "vitrin"
    context.user_data["content_id"] = content["human_id"]
    await send_step_prompt(update, context, "vitrin_category")


async def start_hayat_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_channel_membership(update, context, "hayat"):
        return

    get_or_create_user(update.effective_user)
    content = create_content(update.effective_user.id, "hayat")
    context.user_data.clear()
    context.user_data["flow"] = "hayat"
    context.user_data["content_id"] = content["human_id"]
    await send_step_prompt(update, context, "hayat_city")


async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)


async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, content):
    context.user_data["post_step"] = "preview"
    await update.message.reply_text(
        content_preview_text(content),
        reply_markup=preview_keyboard(content),
    )


async def submit_content(update: Update, context: ContextTypes.DEFAULT_TYPE, content_id):
    content_before_submit = get_content(content_id)
    missing = missing_required_fields(content_before_submit)
    if missing:
        await update.message.reply_text(
            "این draft هنوز کامل نیست.\n\n"
            "فیلدهای ناقص: " + "، ".join(missing),
        )
        return

    content = await submit_content_to_admin(context, content_id)
    context.user_data.clear()
    label = "پیام" if content["content_type"] == "hayat" else "آگهی"
    await update.message.reply_text(
        f"✅ {label} شما برای بررسی ادمین ارسال شد.\n\n🆔 {content['human_id']}",
        reply_markup=MAIN_MENU,
    )


async def handle_interaction_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("interaction_step")
    content_id = context.user_data.get("interaction_content_id")
    if not step or not content_id:
        return False

    text = (update.message.text or "").strip()
    if text == HOME_BUTTON:
        await go_home(update, context)
        return True

    if step == "comment":
        comment = create_comment(content_id, update.effective_user.id, text)
        context.user_data.clear()
        await send_comment_to_admin(context, comment)
        await update.message.reply_text("✅ نظر شما ثبت شد و پس از تایید ادمین نمایش داده می‌شود.")
        return True

    if step == "report":
        report = create_report(content_id, update.effective_user.id, text)
        context.user_data.clear()
        await update.message.reply_text(f"✅ گزارش شما ثبت شد.\n\n🆔 {report['human_id']}")
        return True

    return False


async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if "interaction_step" in context.user_data:
        handled = await handle_interaction_text(update, context)
        if handled:
            return

    if "post_step" not in context.user_data:
        return

    text = (update.message.text or "").strip()
    step = context.user_data["post_step"]
    content_id = context.user_data["content_id"]

    if text == HOME_BUTTON:
        await go_home(update, context)
        return

    if text == BACK_BUTTON:
        await go_home(update, context)
        return

    content = get_content(content_id)
    if not content:
        context.user_data.clear()
        await update.message.reply_text("❌ draft پیدا نشد.", reply_markup=MAIN_MENU)
        return

    if step == "vitrin_category":
        if text not in CATEGORY_OPTIONS:
            await update.message.reply_text("لطفاً یک دسته معتبر انتخاب کنید.")
            return
        update_content(content_id, category=text)
        await send_step_prompt(update, context, "vitrin_city")
        return

    if step == "vitrin_city":
        if len(text) < 2:
            await update.message.reply_text("نام شهر باید حداقل ۲ حرف باشد.")
            return
        update_content(content_id, city=text)
        await send_step_prompt(update, context, "vitrin_title")
        return

    if step == "vitrin_title":
        if len(text) < 3:
            await update.message.reply_text("عنوان باید حداقل ۳ حرف باشد.")
            return
        update_content(content_id, title=text)
        await send_step_prompt(update, context, "vitrin_description")
        return

    if step == "vitrin_description":
        if not is_admin_user(update) and has_restricted_text_content(text):
            await update.message.reply_text(TEXT_RESTRICTION_ERROR)
            return
        if len(text) < 10:
            await update.message.reply_text("توضیحات آگهی خیلی کوتاه است.")
            return
        update_content(content_id, description=text)
        await send_step_prompt(update, context, "vitrin_price")
        return

    if step == "vitrin_price":
        update_content(content_id, price=None if text == SKIP_PRICE else text)
        await send_step_prompt(update, context, "vitrin_media")
        return

    if step == "vitrin_media":
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            content = update_content(content_id, media_file_id=file_id, media_type="photo")
            await show_preview(update, context, content)
            return
        if update.message.video:
            content = update_content(content_id, media_file_id=update.message.video.file_id, media_type="video")
            await show_preview(update, context, content)
            return
        if text == SKIP_MEDIA:
            content = update_content(content_id)
            await show_preview(update, context, content)
            return
        await update.message.reply_text("لطفاً عکس/ویدیو بفرستید یا «بدون عکس/ویدیو» را انتخاب کنید.")
        return

    if step == "hayat_city":
        update_content(content_id, city=None if text == SKIP_CITY else text)
        await send_step_prompt(update, context, "hayat_message")
        return

    if step == "hayat_message":
        if not is_admin_user(update) and has_restricted_text_content(text):
            await update.message.reply_text(TEXT_RESTRICTION_ERROR)
            return
        if len(text) < 5:
            await update.message.reply_text("متن پیام خیلی کوتاه است.")
            return
        content = update_content(content_id, description=text, anonymous_author="ناشناس")
        context.user_data["post_step"] = "hayat_confirm"
        await update.message.reply_text(
            content_preview_text(content),
            reply_markup=list_keyboard([CONFIRM_HAYAT, EDIT_HAYAT, ARCHIVE_HAYAT], include_back=False),
        )
        return

    if step == "hayat_confirm":
        if text == CONFIRM_HAYAT:
            await submit_content(update, context, content_id)
            return
        if text == EDIT_HAYAT:
            await send_step_prompt(update, context, "hayat_message")
            return
        if text == ARCHIVE_HAYAT:
            archive_content(content_id, update.effective_user.id)
            context.user_data.clear()
            await update.message.reply_text("🗄 پیام آرشیو شد.", reply_markup=MAIN_MENU)
            return
        await update.message.reply_text("لطفاً یکی از گزینه‌های تایید، ویرایش یا آرشیو را انتخاب کنید.")


async def draft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    _, action, content_id = query.data.split(":")
    content = get_content(content_id)
    if not content:
        await query.edit_message_text("❌ محتوا پیدا نشد.")
        return

    if content["user_telegram_id"] != query.from_user.id:
        await query.edit_message_text("فقط صاحب محتوا می‌تواند این عملیات را انجام دهد.")
        return

    if action == "preview":
        await query.message.reply_text(content_preview_text(content), reply_markup=preview_keyboard(content))
        return

    if action == "archive":
        archive_content(content_id, query.from_user.id)
        await query.edit_message_text("🗄 محتوا آرشیو شد.")
        return

    if action == "submit":
        missing = missing_required_fields(content)
        if missing:
            await query.edit_message_text(
                "این draft هنوز کامل نیست.\n\n"
                "فیلدهای ناقص: " + "، ".join(missing),
            )
            return

        await submit_content_to_admin(context, content_id)
        await query.edit_message_text(f"✅ برای بررسی ادمین ارسال شد.\n\n🆔 {content_id}")
        return

    if action == "edit":
        context.user_data.clear()
        context.user_data["content_id"] = content_id
        context.user_data["flow"] = content["content_type"]
        if content["content_type"] == "hayat":
            await query.message.reply_text(STEP_PROMPTS["hayat_message"], reply_markup=step_keyboard("hayat_message"))
            context.user_data["post_step"] = "hayat_message"
        else:
            await query.message.reply_text(STEP_PROMPTS["vitrin_title"], reply_markup=step_keyboard("vitrin_title"))
            context.user_data["post_step"] = "vitrin_title"


async def published_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    _, action, content_id = query.data.split(":")
    content = get_content(content_id)
    if not content:
        await query.answer("محتوا پیدا نشد.", show_alert=True)
        return

    if action in ("like", "dislike"):
        save_reaction(content_id, query.from_user.id, action)
        await query.answer("رأی شما ثبت شد.", show_alert=False)
        return

    if action == "comment":
        context.user_data.clear()
        context.user_data["interaction_step"] = "comment"
        context.user_data["interaction_content_id"] = content_id
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"💬 نظر خود را برای {content_id} بنویسید:",
        )
        return

    if action == "report":
        context.user_data.clear()
        context.user_data["interaction_step"] = "report"
        context.user_data["interaction_content_id"] = content_id
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"🚩 دلیل گزارش {content_id} را بنویسید:",
        )
        return

    if action == "comments":
        comments = list_approved_comments(content_id)
        if not comments:
            await context.bot.send_message(chat_id=query.from_user.id, text="هنوز نظری تایید نشده است.")
            return
        text = "💬 نظرات تاییدشده\n\n" + "\n\n".join(
            f"{comment['human_id']}:\n{comment['body']}" for comment in comments
        )
        await context.bot.send_message(chat_id=query.from_user.id, text=text)


async def user_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await draft_callback(update, context)
