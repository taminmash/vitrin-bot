from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_or_create_user, list_user_content
from handlers.common import draft_actions_keyboard, home_keyboard


STATUS_LABELS = {
    "draft": "Draft فعال",
    "needs_edit": "نیازمند ویرایش",
    "pending_review": "در انتظار بررسی",
    "published": "منتشر شده",
    "archived": "آرشیو شده",
    "rejected": "رد شده",
}


def profile_item_text(content):
    label = "پیام حیاط خلوت" if content["content_type"] == "hayat" else "آگهی ویترین"
    title = content.get("title") or content.get("description") or "-"
    if len(title) > 80:
        title = title[:77] + "..."
    return (
        f"{label}\n"
        f"🆔 {content['human_id']}\n"
        f"وضعیت: {STATUS_LABELS.get(content['status'], content['status'])}\n"
        f"{title}"
    )


async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user = get_or_create_user(update.effective_user)
    items = list_user_content(update.effective_user.id)

    await update.message.reply_text(
        "👤 پروفایل من\n\n"
        f"شناسه کاربری: {user.get('human_id') or '-'}\n"
        f"نام: {update.effective_user.first_name or '-'}\n\n"
        "Draft Manager:",
        reply_markup=home_keyboard(),
    )

    if not items:
        await update.message.reply_text("هنوز draft یا محتوایی ثبت نشده است.", reply_markup=home_keyboard())
        return

    for content in items:
        reply_markup = None
        if content["status"] in ("draft", "needs_edit"):
            reply_markup = draft_actions_keyboard(content)
        await update.message.reply_text(profile_item_text(content), reply_markup=reply_markup)


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return
