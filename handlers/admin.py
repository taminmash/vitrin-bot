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

BOT_USERNAME = "@VitrinSpainBot"


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
                "📝 ویرایش آگهی",
                callback_data=f"edit:{post_id}",
            )
        ],
        [
            InlineKeyboardButton(
                "❌ حذف آگهی",
                callback_data=f"reject:{post_id}",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def build_category_label(category, subcategory):
    if subcategory:
        return f"{category} » {subcategory}"
    return category


async def send_post_to_admin(
    context: ContextTypes.DEFAULT_TYPE,
    post_id: int,
    post_data: dict,
):

    category_label = build_category_label(
        post_data.get("category", ""),
        post_data.get("subcategory", ""),
    )

    text = f"""
📥 آگهی جدید

🆔 {post_id}

📂 دسته:
{category_label}

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
            subcategory,
            city,
            display_name,
            telegram_id,
            content,
            status,
            channel_message_id,
        ) = post

        category_label = build_category_label(category, subcategory)

        channel_text = f"""🆔 ID: {post_id}

📂 دسته:
{category_label}

━━━━━━━━━━━━━━

📝 متن آگهی:

{content}

━━━━━━━━━━━━━━

📍 شهر:
{city}

👤 کاربر:
{telegram_id}

🤖 ربات:
{BOT_USERNAME}
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

    if data.startswith("edit:"):

        post_id = int(data.split(":")[1])

        context.user_data["awaiting_edit_reason"] = post_id

        await query.edit_message_text(
            "📝 لطفاً دلیل درخواست ویرایش را وارد کنید:"
        )

        return

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


async def admin_edit_reason_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if "awaiting_edit_reason" not in context.user_data:
        return

    post_id = context.user_data.pop("awaiting_edit_reason")

    reason = update.message.text

    update_post_status(
        post_id,
        "need_edit",
    )

    user_id = get_user_id_by_post(post_id)

    if user_id:

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "📝 آگهی شما نیاز به ویرایش دارد.\n\n"
                f"دلیل ویرایش:\n{reason}\n\n"
                "لطفاً پیام خود را ویرایش و مجدداً ارسال کنید."
            ),
        )

    await update.message.reply_text(
        f"✅ درخواست ویرایش برای آگهی {post_id} ارسال شد."
    )
