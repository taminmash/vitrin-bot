from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update

from telegram.ext import ContextTypes

from config_v2 import ADMIN_IDS
from config_v2 import CHANNEL_VITRIN

from database.db import get_post
from database.db import update_post_status
from database.db import save_channel_message
from database.db import get_user_id_by_post


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


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data

    #
    # تایید انتشار
    #
    if data.startswith("approve:"):

        post_id = int(data.split(":")[1])

        post = get_post(post_id)

        if not post:

            await query.edit_message_text(
                "❌ آگهی پیدا نشد."
            )

            return

        (
            _id,
            user_id,
            category,
            city,
            display_name,
            telegram_id,
            content,
            status,
            channel_message_id,
        ) = post

        channel_text = f"""
📂 {category}

📍 {city}

👤 {display_name}

📨 {telegram_id}

━━━━━━━━━━━━━━

{content}
"""

        msg = await context.bot.send_message(
            chat_id=CHANNEL_VITRIN,
            text=channel_text,
        )

        save_channel_message(
            post_id,
            msg.message_id,
        )

        update_post_status(
            post_id,
            "approved",
        )

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ آگهی شما تایید و منتشر شد.",
        )

        await query.edit_message_text(
            f"✅ آگهی {post_id} منتشر شد."
        )

        return

    #
    # درخواست اصلاح
    #
    if data.startswith("edit:"):

        post_id = int(data.split(":")[1])

        update_post_status(
            post_id,
            "need_edit",
        )

        user_id = get_user_id_by_post(post_id)

        if user_id:

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "📝 آگهی شما نیاز به اصلاح دارد.\n\n"
                    "لطفاً آگهی جدید ثبت کنید."
                ),
            )

        await query.edit_message_text(
            f"📝 درخواست اصلاح برای آگهی {post_id} ارسال شد."
        )

        return

    #
    # رد آگهی
    #
    if data.startswith("reject:"):

        post_id = int(data.split(":")[1])

        update_post_status(
            post_id,
            "rejected",
        )

        user_id = get_user_id_by_post(post_id)

        if user_id:

            await context.bot.send_message(
                chat_id=user_id,
                text="❌ آگهی شما تایید نشد.",
            )

        await query.edit_message_text(
            f"❌ آگهی {post_id} رد شد."
        )

        return
