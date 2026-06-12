from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_comment_count, get_comments, add_comment


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

    post_id = int(query.data.split(":")[1])

    comments = get_comments(post_id)

    if not comments:
        text = "💬 هنوز نظری ثبت نشده است."
    else:
        text = "💬 نظرات:\n\n"
        for i, comment in enumerate(comments, start=1):
            text += f"{i}. {comment[0]}\n"

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text=text
    )

    context.user_data["waiting_comment_post_id"] = post_id

    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="✍️ حالا نظر خود را ارسال کنید."
    )


async def save_comment(update, context):
    if "waiting_comment_post_id" not in context.user_data:
        return

    post_id = context.user_data["waiting_comment_post_id"]

    user_id = update.effective_user.id
    nickname = f"کاربر {str(user_id)[-4:]}"

    add_comment(
        post_id,
        user_id,
        nickname,
        update.message.text
    )

    del context.user_data["waiting_comment_post_id"]

    await update.message.reply_text(
        "✅ نظر شما ثبت شد."
    )
