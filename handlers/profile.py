from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import HOME_BUTTON
from database.db import count_user_content_by_status, get_or_create_user, list_user_content
from handlers.common import draft_actions_keyboard


PROFILE_DRAFTS = "📝 پیش‌نویس‌های من"
PROFILE_PENDING = "⏳ در انتظار بررسی"
PROFILE_PUBLISHED = "✅ منتشر شده‌ها"

PROFILE_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(PROFILE_DRAFTS)],
        [KeyboardButton(PROFILE_PENDING)],
        [KeyboardButton(PROFILE_PUBLISHED)],
        [KeyboardButton("🏠 بازگشت به خانه")],
    ],
    resize_keyboard=True,
)

STATUS_LABELS = {
    "draft": "draft",
    "needs_edit": "needs_edit",
    "pending_review": "pending_review",
    "published": "published",
    "archived": "archived",
    "rejected": "rejected",
    "deleted": "deleted",
}


def profile_item_text(content):
    title = content.get("title") or content.get("description") or "-"
    if len(title) > 80:
        title = title[:77] + "..."
    return (
        f"🆔 {content['human_id']}\n"
        f"وضعیت: {STATUS_LABELS.get(content['status'], content['status'])}\n"
        f"{title}"
    )


async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["profile_step"] = "menu"
    user = get_or_create_user(update.effective_user)
    counts = count_user_content_by_status(update.effective_user.id)
    draft_count = counts.get("draft", 0) + counts.get("needs_edit", 0)
    pending_count = counts.get("pending_review", 0)
    published_count = counts.get("published", 0)

    await update.message.reply_text(
        "👤 پروفایل\n\n"
        "شناسه کاربری:\n"
        f"{user.get('human_id') or '-'}\n\n"
        "📊 وضعیت حساب:\n"
        "کاربر عادی\n\n"
        "📝 پیش‌نویس‌ها:\n"
        f"{draft_count}\n\n"
        "⏳ در انتظار بررسی:\n"
        f"{pending_count}\n\n"
        "✅ منتشر شده:\n"
        f"{published_count}",
        reply_markup=PROFILE_KEYBOARD,
    )


async def show_profile_items(update: Update, statuses):
    items = [item for item in list_user_content(update.effective_user.id) if item["status"] in statuses]
    if not items:
        await update.message.reply_text("موردی برای نمایش وجود ندارد.", reply_markup=PROFILE_KEYBOARD)
        return

    for content in items:
        reply_markup = None
        if content["status"] in ("draft", "needs_edit"):
            reply_markup = draft_actions_keyboard(content)
        await update.message.reply_text(profile_item_text(content), reply_markup=reply_markup)


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("profile_step") != "menu" or not update.message:
        return

    text = update.message.text
    if text in (HOME_BUTTON, "🏠 بازگشت به خانه"):
        context.user_data.clear()
        from handlers.start import MAIN_MENU

        await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
        return

    if text == PROFILE_DRAFTS:
        await show_profile_items(update, {"draft", "needs_edit", "archived", "rejected"})
        return
    if text == PROFILE_PENDING:
        await show_profile_items(update, {"pending_review"})
        return
    if text == PROFILE_PUBLISHED:
        await show_profile_items(update, {"published"})
