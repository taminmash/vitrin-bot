from telegram import Update
from telegram.ext import ContextTypes

from config_v2 import (
    CHANNEL_ID,
    POST_STATUS_DELETED,
    POST_STATUS_NEEDS_EDIT,
    POST_STATUS_PUBLISHED,
)
from database.db import get_post, mark_post_published, update_post_status
from handlers.common import admin_post_text, channel_post_text


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    action = parts[1]
    post_id = int(parts[2])

    post = get_post(post_id)
    if not post:
        await query.edit_message_text("آگهی پیدا نشد.")
        return

    if action == "approve":
        if post["status"] == POST_STATUS_DELETED:
            await query.edit_message_text("این آگهی قبلاً حذف شده است.")
            return

        sent = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=channel_post_text(post),
        )
        post = mark_post_published(post_id, sent.message_id)

        await context.bot.send_message(
            chat_id=post["telegram_id"],
            text="✅ آگهی شما تایید و منتشر شد.",
        )
        await query.edit_message_text(
            "✅ آگهی تایید شد.\n\n" + admin_post_text(post)
        )
        return

    if action == "edit":
        post = update_post_status(post_id, POST_STATUS_NEEDS_EDIT)
        await context.bot.send_message(
            chat_id=post["telegram_id"],
            text=(
                "📝 آگهی شما نیازمند ویرایش است.\n\n"
                "لطفاً از پنل مدیریت آگهی، گزینه ویرایش آگهی را بزنید."
            ),
        )
        await query.edit_message_text(
            "📝 درخواست ویرایش برای کاربر ارسال شد.\n\n" + admin_post_text(post)
        )
        return

    if action == "delete":
        if post.get("channel_message_id"):
            try:
                await context.bot.delete_message(
                    chat_id=CHANNEL_ID,
                    message_id=post["channel_message_id"],
                )
            except Exception:
                pass

        post = update_post_status(post_id, POST_STATUS_DELETED)
        await context.bot.send_message(
            chat_id=post["telegram_id"],
            text="❌ آگهی شما توسط ادمین حذف شد.",
        )
        await query.edit_message_text(
            "❌ آگهی حذف شد.\n\n" + admin_post_text(post)
        )
        return

    if action == POST_STATUS_PUBLISHED:
        return
