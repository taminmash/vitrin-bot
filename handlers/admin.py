from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import ADMIN_IDS, CHANNEL_HAYAT, CHANNEL_VITRIN
from database.db import (
    get_comment,
    get_content,
    list_active_reports,
    list_pending_content,
    resolve_comment,
    resolve_review,
    save_publication,
    submit_for_review,
)
from handlers.common import (
    admin_comment_keyboard,
    admin_content_text,
    admin_review_keyboard,
    category_label,
    channel_post_text,
    published_keyboard,
    is_hayat_content,
)


ADMIN_PENDING = "📥 موارد در انتظار بررسی"
ADMIN_REPORTS = "🚩 گزارش‌ها"
ADMIN_BACK = "🏠 بازگشت"
ADMIN_PANEL_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(ADMIN_PENDING)],
        [KeyboardButton(ADMIN_REPORTS)],
        [KeyboardButton(ADMIN_BACK)],
    ],
    resize_keyboard=True,
)


def is_admin(user_id):
    return user_id in ADMIN_IDS


async def send_content_to_admin(context: ContextTypes.DEFAULT_TYPE, content):
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_content_text(content),
            reply_markup=admin_review_keyboard(content["human_id"]),
        )


async def submit_content_to_admin(context: ContextTypes.DEFAULT_TYPE, content_human_id):
    content, _ = submit_for_review(content_human_id)
    await send_content_to_admin(context, content)
    return content


async def send_comment_to_admin(context: ContextTypes.DEFAULT_TYPE, comment):
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                "💬 نظر جدید برای بررسی\n\n"
                f"🆔 {comment['human_id']}\n"
                f"محتوا: {comment.get('content_human_id') or '-'}\n\n"
                f"{comment['body']}"
            ),
            reply_markup=admin_comment_keyboard(comment["human_id"]),
        )


async def publish_content(context: ContextTypes.DEFAULT_TYPE, content):
    channel_id = CHANNEL_HAYAT if is_hayat_content(content) else CHANNEL_VITRIN
    kwargs = {
        "chat_id": channel_id,
        "caption" if content.get("media_file_id") else "text": channel_post_text(content),
        "parse_mode": "HTML",
        "reply_markup": published_keyboard(content["human_id"]),
    }

    if content.get("media_file_id") and content.get("media_type") == "photo":
        msg = await context.bot.send_photo(photo=content["media_file_id"], **kwargs)
    elif content.get("media_file_id") and content.get("media_type") == "video":
        msg = await context.bot.send_video(video=content["media_file_id"], **kwargs)
    else:
        msg = await context.bot.send_message(**kwargs)

    save_publication(content["human_id"], channel_id, msg.message_id)
    return msg


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, action, object_id = parts

    if action == "approve":
        content = get_content(object_id)
        if not content or content["status"] != "pending_review":
            await query.edit_message_text("این محتوا دیگر در وضعیت بررسی نیست.")
            return

        await publish_content(context, content)
        resolve_review(object_id, query.from_user.id, "approve")
        label = "پیام" if is_hayat_content(content) else "آگهی"
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=f"✅ {label} شما تایید و منتشر شد.\n\n🆔 {content['human_id']}",
        )
        await query.edit_message_text(f"✅ منتشر شد: {content['human_id']}")
        return

    if action in ("need_edit", "reject", "delete"):
        content = get_content(object_id)
        if not content:
            await query.edit_message_text("❌ محتوا پیدا نشد.")
            return

        context.user_data["admin_reason_action"] = action
        context.user_data["admin_reason_content_id"] = object_id
        prompt = {
            "need_edit": "📝 دلیل نیاز به ویرایش را ارسال کنید:",
            "reject": "📝 دلیل رد شدن محتوا را ارسال کنید:",
            "delete": "📝 دلیل حذف محتوا را ارسال کنید:",
        }[action]
        await query.edit_message_text(prompt)
        return


async def comment_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    _, action, comment_id = query.data.split(":")
    comment = get_comment(comment_id)
    if not comment:
        await query.edit_message_text("❌ نظر پیدا نشد.")
        return

    if action == "approve":
        resolve_comment(comment_id, query.from_user.id, "approve")
        await query.edit_message_text(f"✅ نظر {comment_id} تایید شد.")
        return

    context.user_data["admin_comment_reject_id"] = comment_id
    await query.edit_message_text("📝 دلیل رد نظر را ارسال کنید:")


async def admin_edit_reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.effective_user.id):
        return

    text = update.message.text
    if context.user_data.get("admin_panel") and not (
        context.user_data.get("admin_comment_reject_id")
        or context.user_data.get("admin_reason_action")
    ):
        if text == ADMIN_PENDING:
            await show_pending_admin_items(update)
            return
        if text == ADMIN_REPORTS:
            await show_admin_reports(update)
            return
        if text == ADMIN_BACK:
            context.user_data.pop("admin_panel", None)
            from handlers.start import MAIN_MENU

            await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
            return

    comment_id = context.user_data.pop("admin_comment_reject_id", None)
    if comment_id:
        reason = update.message.text.strip()
        resolve_comment(comment_id, update.effective_user.id, "reject", reason)
        await update.message.reply_text(f"❌ نظر {comment_id} رد شد.")
        return

    action = context.user_data.pop("admin_reason_action", None)
    content_id = context.user_data.pop("admin_reason_content_id", None)
    if not action or not content_id:
        return

    reason = update.message.text.strip()
    content = get_content(content_id)
    if not content:
        await update.message.reply_text("❌ محتوا پیدا نشد.")
        return

    resolve_review(content_id, update.effective_user.id, action, reason)
    label = "پیام" if is_hayat_content(content) else "آگهی"

    if action == "need_edit":
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=(
                f"↩️ {label} شما نیاز به ویرایش دارد.\n\n"
                f"🆔 {content['human_id']}\n\n"
                f"دلیل ادمین:\n{reason}"
            ),
        )
        await update.message.reply_text(f"✅ {content_id} به draft برگشت.")
        return

    if action == "reject":
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=(
                f"❌ {label} شما رد شد.\n\n"
                f"🆔 {content['human_id']}\n\n"
                f"دلیل ادمین:\n{reason}"
            ),
        )
        await update.message.reply_text(f"✅ {content_id} رد شد.")
        return

    await context.bot.send_message(
        chat_id=content["user_telegram_id"],
        text=(
            f"🗑 {label} شما حذف شد.\n\n"
            f"🆔 {content['human_id']}\n\n"
            f"دلیل ادمین:\n{reason}"
        ),
    )
    await update.message.reply_text(f"✅ {content_id} حذف شد.")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی ادمین ندارید.")
        return

    context.user_data["admin_panel"] = True
    await update.message.reply_text(
        "👨‍💼 پنل ادمین ویترین",
        reply_markup=ADMIN_PANEL_KEYBOARD,
    )


async def show_pending_admin_items(update: Update):
    pending = list_pending_content()
    if not pending:
        await update.message.reply_text("موردی در انتظار بررسی وجود ندارد.", reply_markup=ADMIN_PANEL_KEYBOARD)
        return

    for content in pending:
        await update.message.reply_text(
            admin_content_text(content),
            reply_markup=admin_review_keyboard(content["human_id"]),
        )


async def show_admin_reports(update: Update):
    reports = list_active_reports()
    if reports:
        text = "🚩 گزارش‌های فعال\n\n" + "\n".join(
            f"{report['human_id']} برای {report['content_human_id']}: {report['reason']}"
            for report in reports
        )
        await update.message.reply_text(text, reply_markup=ADMIN_PANEL_KEYBOARD)
    else:
        await update.message.reply_text("گزارش فعالی وجود ندارد.", reply_markup=ADMIN_PANEL_KEYBOARD)
