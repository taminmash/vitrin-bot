from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config_v2 import BACK_BUTTON, BOT_USERNAME


SEPARATOR = "━━━━━━━━━━━━━━"


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


def category_label(category, subcategory):
    return f"{category} » {subcategory}" if subcategory else category


def channel_post_text(post):
    return (
        f"🆔 ID: {post['id']}\n\n"
        f"📂 {category_label(post['category'], post.get('subcategory'))}\n\n"
        f"{SEPARATOR}\n\n"
        f"📝 {post['content']}\n\n"
        f"{SEPARATOR}\n\n"
        f"📍 {post.get('city') or '-'}\n"
        f"👤 {post.get('display_name') or '-'}\n"
        f"🤖 @{BOT_USERNAME}"
    )


def admin_post_text(post):
    return (
        f"📥 آگهی جدید\n\n"
        f"{channel_post_text(post)}\n\n"
        f"تلگرام کاربر: {post.get('telegram_id') or '-'}"
    )


def admin_keyboard(post_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ تایید انتشار", callback_data=f"admin:approve:{post_id}")],
            [InlineKeyboardButton("📝 نیاز به ویرایش", callback_data=f"admin:need_edit:{post_id}")],
            [InlineKeyboardButton("❌ حذف آگهی", callback_data=f"admin:delete:{post_id}")],
        ]
    )


def user_manage_keyboard(post_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ ویرایش آگهی", callback_data=f"userpost:edit:{post_id}")],
            [InlineKeyboardButton("🗑️ حذف آگهی", callback_data=f"userpost:delete:{post_id}")],
        ]
    )
