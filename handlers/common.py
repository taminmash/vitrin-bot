from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config_v2 import BACK_BUTTON, BOT_USERNAME


def back_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BACK_BUTTON)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def list_keyboard(items, include_back=True):
    rows = [[KeyboardButton(item)] for item in items]
    if include_back:
        rows.append([KeyboardButton(BACK_BUTTON)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def admin_post_text(post):
    return (
        f"🆔 ID: {post['id']}\n\n"
        f"📂 دسته:\n"
        f"{post['category']} » {post.get('subcategory') or '-'}\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📝 متن آگهی:\n\n"
        f"{post['content']}\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📍 شهر:\n"
        f"{post.get('city') or '-'}\n\n"
        f"👤 کاربر:\n"
        f"{post['telegram_id']}\n\n"
        f"🤖 ربات:\n"
        f"@{BOT_USERNAME}"
    )


def channel_post_text(post):
    return (
        f"🆔 ID: {post['id']}\n\n"
        f"📂 دسته:\n"
        f"{post['category']} » {post.get('subcategory') or '-'}\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📝 متن آگهی:\n\n"
        f"{post['content']}\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📍 شهر:\n"
        f"{post.get('city') or '-'}\n\n"
        f"👤 کاربر:\n"
        f"{post['telegram_id']}\n\n"
        f"🤖 @{BOT_USERNAME}"
    )


def admin_keyboard(post_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید آگهی", callback_data=f"admin:approve:{post_id}"),
            ],
            [
                InlineKeyboardButton("📝 درخواست ویرایش", callback_data=f"admin:edit:{post_id}"),
                InlineKeyboardButton("🗑️ حذف آگهی", callback_data=f"admin:delete:{post_id}"),
            ],
        ]
    )


def user_manage_keyboard(post_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ ویرایش آگهی", callback_data=f"userpost:edit:{post_id}"),
            ],
            [
                InlineKeyboardButton("🗑️ حذف آگهی", callback_data=f"userpost:delete:{post_id}"),
            ],
            [
                InlineKeyboardButton("📊 وضعیت آگهی", callback_data=f"userpost:status:{post_id}"),
            ],
        ]
    )
