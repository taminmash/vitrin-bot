from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_comment_count


def build_comment_button(post_id):
    count = get_comment_count(post_id)

    keyboard = [[
        InlineKeyboardButton(
            f"💬 {count} نظر",
            callback_data=f"comment:{post_id}"
        )
    ]]

    return InlineKeyboardMarkup(keyboard)
