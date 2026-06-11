from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_comment_count, get_comments


def build_comment_button(post_id):
    count = get_comment_count(post_id)

    keyboard = [[
        InlineKeyboardButton(
            f"💬 {count} نظر",
            callback_data=f"comment:{post_id}"
        )
    ]]

    return InlineKeyboardMarkup(keyboard)


async def comment_callback(update, context):
    query = update.callback_query
    await query.answer()

    post_id = query.data.split(":")[1]

    await query.message.reply_text(
        f"✍️ ارسال نظر برای پست {post_id}\n\nاین بخش فعال شد."
    )
