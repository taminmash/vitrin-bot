from telegram import Update
from telegram.ext import ContextTypes

from config_v2 import ADMIN_IDS, CHANNEL_VITRIN
from database.db import get_post, save_channel_message, update_post_status
from handlers.common import (
    SEPARATOR,
    admin_keyboard,
    admin_post_text,
    category_label,
    channel_post_text,
    user_manage_keyboard,
)


async def send_post_to_admin(context: ContextTypes.DEFAULT_TYPE, post_id: int):
    post = get_post(post_id)
    if not post:
        return

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_post_text(post),
            reply_markup=admin_keyboard(post_id),
        )


def edit_request_text(post, reason):
    return (
        "✏️ درخواست ویرایش آگهی\n\n"
        f"🆔 شماره آگهی: {post['id']}\n\n"
        "📂 دسته » زیر‌دسته:\n"
        f"{category_label(post['category'], post.get('subcategory'))}\n\n"
        f"{SEPARATOR}\n\n"
        "📝 متن آگهی:\n"
        f"{post['content']}\n\n"
        f"{SEPARATOR}\n\n"
        f"📍 شهر: {post.get('city') or '-'}\n"
        f"👤 نام نمایشی: {post.get('display_name') or '-'}\n\n"
        f"{SEPARATOR}\n\n"
        "✏️ دلیل ویرایش:\n"
        f"{reason}"
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, action, post_id_text = parts
    post_id = int(post_id_text)
    post = get_post(post_id)

    if not post:
        await query.edit_message_text("❌ آگهی پیدا نشد.")
        return

    if action == "approve":
        if post["status"] != "pending":
            await query.edit_message_text("این آگهی دیگر در وضعیت pending نیست.")
            return

        msg = await context.bot.send_message(
            chat_id=CHANNEL_VITRIN,
            text=channel_post_text(post),
            parse_mode="HTML",
        )
        save_channel_message(post_id, msg.message_id)
        update_post_status(post_id, "approved", approved_by=query.from_user.id)

        await context.bot.send_message(
            chat_id=post["user_id"],
            text=(
                "✅ آگهی شما تایید و منتشر شد.\n\n"
                f"📂 {category_label(post['category'], post.get('subcategory'))}"
            ),
        )
        await query.edit_message_text(f"✅ آگهی {post_id} منتشر شد.")
        return

    if action == "need_edit":
        if post["status"] != "pending":
            await query.edit_message_text("فقط آگهی pending می‌تواند نیاز به ویرایش بگیرد.")
            return

        context.user_data["awaiting_edit_reason_post_id"] = post_id
        await query.edit_message_text("📝 دلیل نیاز به ویرایش را ارسال کنید:")
        return

    if action == "delete":
        update_post_status(post_id, "deleted_by_admin")
        await context.bot.send_message(
            chat_id=post["user_id"],
            text=(
                "❌ آگهی شما حذف شد.\n\n"
                f"📂 {category_label(post['category'], post.get('subcategory'))}"
            ),
        )
        await query.edit_message_text(f"❌ آگهی {post_id} حذف شد.")


async def admin_edit_reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if update.effective_user.id not in ADMIN_IDS:
        return

    post_id = context.user_data.pop("awaiting_edit_reason_post_id", None)
    if not post_id:
        return

    reason = update.message.text.strip()
    post = get_post(post_id)
    if not post:
        await update.message.reply_text("❌ آگهی پیدا نشد.")
        return

    update_post_status(post_id, "need_edit")
    await context.bot.send_message(
        chat_id=post["user_id"],
        text=edit_request_text(post, reason),
        reply_markup=user_manage_keyboard(post_id),
    )
    await update.message.reply_text(f"✅ درخواست ویرایش برای آگهی {post_id} ارسال شد.")
