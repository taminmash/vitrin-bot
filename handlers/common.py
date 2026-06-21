import html
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config_v2 import BACK_BUTTON, BOT_USERNAME, HOME_BUTTON


SEPARATOR = "━━━━━━━━━━━━━━"


def back_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BACK_BUTTON)], [KeyboardButton(HOME_BUTTON)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def list_keyboard(items, include_back=True, include_home=True):
    rows = [[KeyboardButton(item)] for item in items]
    if include_back:
        rows.append([KeyboardButton(BACK_BUTTON)])
    if include_home:
        rows.append([KeyboardButton(HOME_BUTTON)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def category_label(category, subcategory):
    return f"{category} » {subcategory}" if subcategory else category


def clean_label(value):
    value = value or ""
    value = re.sub(r"[^\w\s\u200c]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def hashtagify(value):
    cleaned = clean_label(value).replace("\u200c", " ")
    tag = re.sub(r"\s+", "_", cleaned).strip("_")
    return f"#{tag}" if tag else None


def post_hashtags(post):
    tags = []
    for value in (post.get("category"), post.get("subcategory"), post.get("city")):
        tag = hashtagify(value)
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) == 3:
            break
    return " ".join(tags)


def linked_display_name(post):
    display_name = html.escape(post.get("display_name") or "-")
    telegram_id = post.get("telegram_id") or ""

    if telegram_id.startswith("@") and len(telegram_id) > 1:
        username = telegram_id[1:]
        if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            return f'<a href="https://t.me/{username}">{display_name}</a>'

    return display_name


def channel_post_text(post):
    hashtags = post_hashtags(post)
    category = html.escape(category_label(clean_label(post.get("category")), clean_label(post.get("subcategory"))))
    content = html.escape(post.get("content") or "")
    city = html.escape(post.get("city") or "-")
    display_name = linked_display_name(post)

    return (
        f"🆔 {post['id']}\n\n"
        f"{hashtags}\n\n"
        f"{category}\n\n"
        f"{SEPARATOR}\n\n"
        f"📝 {content}\n\n"
        f"{SEPARATOR}\n\n"
        f"📍 {city}\n"
        f"👤 {display_name}\n"
        f"🤖 @{BOT_USERNAME}"
    )


def admin_post_text(post):
    return (
        "📥 آگهی جدید\n\n"
        f"🆔 ID: {post['id']}\n\n"
        f"📂 {category_label(post['category'], post.get('subcategory'))}\n\n"
        f"{SEPARATOR}\n\n"
        f"📝 {post['content']}\n\n"
        f"{SEPARATOR}\n\n"
        f"📍 {post.get('city') or '-'}\n"
        f"👤 {post.get('display_name') or '-'}\n"
        f"🤖 @{BOT_USERNAME}\n\n"
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
            [InlineKeyboardButton(HOME_BUTTON, callback_data="userpost:home:0")],
        ]
    )
