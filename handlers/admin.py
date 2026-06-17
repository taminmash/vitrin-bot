from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update

from telegram.ext import ContextTypes

from config_v2 import ADMIN_IDS


def build_admin_keyboard(post_id):

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ تایید انتشار",
                callback_data=f"approve:{post_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "📝 درخواست اصلاح",
                callback_data=f"edit:{post_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ رد آگهی",
                callback_data=f"reject:{post_id}",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


async def send_post_to_admin(
    context: ContextTypes.DEFAULT_TYPE,
    post_id: int,
    post_data: dict,
):

    text = f"""
📥 آگهی جدید

🆔 {post_id}

📂 دسته:
{post_data['category']}

📍 شهر:
{post_data['city']}

👤 نام:
{post_data['display_name']}

📨 تلگرام:
{post_data['telegram_id']}

📝 متن:

{post_data['content']}
"""

    for admin_id in ADMIN_IDS:

        await context.bot.send_message(
            chat_id=admin_id,
            text=text,
            reply_markup=build_admin_keyboard(post_id),
        )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data

    if data.startswith("approve:"):

        await query.edit_message_text(
            "✅ آگهی تایید شد."
        )

        return

    if data.startswith("edit:"):

        await query.edit_message_text(
            "📝 درخواست اصلاح ثبت شد."
        )

        return

    if data.startswith("reject:"):

        await query.edit_message_text(
            "❌ آگهی رد شد."
        )

        return
