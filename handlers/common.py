import html
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config_v2 import BACK_BUTTON, BOT_USERNAME, HOME_BUTTON


SEPARATOR = "━━━━━━━━━━━━━━"


def home_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton(HOME_BUTTON)]],
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


def category_label(category, subcategory=None):
    return f"{category} » {subcategory}" if subcategory else category or "-"


def clean_label(value):
    value = value or ""
    value = re.sub(r"[^\w\s\u200c]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def hashtagify(value):
    cleaned = clean_label(value).replace("\u200c", " ")
    tag = re.sub(r"\s+", "_", cleaned).strip("_")
    return f"#{tag}" if tag else None


def vitrin_hashtags(content):
    tags = []
    for value in (content.get("category"), content.get("city"), "ویترین_اسپانیا"):
        tag = hashtagify(value)
        if tag and tag not in tags:
            tags.append(tag)
    return " ".join(tags[:5])


def hayat_hashtags():
    return "\n".join(
        [
            "#حیاط_خلوت",
            "#پیام_ناشناس",
            "#اسپانیا",
            "#زندگی_در_اسپانیا",
        ]
    )


def content_label(content):
    return "پیام حیاط خلوت" if content.get("content_type") == "hayat" else "آگهی ویترین"


def content_preview_text(content):
    if content.get("content_type") == "hayat":
        city = content.get("city") or "ثبت نشده"
        return (
            "پیش‌نمایش پیام ناشناس حیاط خلوت\n\n"
            f"🆔 {content['human_id']}\n"
            f"📍 شهر: {city}\n\n"
            f"{SEPARATOR}\n\n"
            f"{content.get('description') or '-'}\n\n"
            f"{SEPARATOR}\n\n"
            "هیچ نام کاربری، آیدی تلگرام یا لینک پروفایل منتشر نمی‌شود."
        )

    price = content.get("price") or "توافقی / ثبت نشده"
    media = "دارد" if content.get("media_file_id") else "ندارد"
    return (
        "پیش‌نمایش آگهی ویترین\n\n"
        f"🆔 {content['human_id']}\n"
        f"📂 دسته: {content.get('category') or '-'}\n"
        f"📍 شهر: {content.get('city') or '-'}\n"
        f"🏷 عنوان: {content.get('title') or '-'}\n"
        f"💶 قیمت: {price}\n"
        f"🖼 رسانه: {media}\n\n"
        f"{SEPARATOR}\n\n"
        f"{content.get('description') or '-'}"
    )


def vitrin_channel_text(content):
    hashtags = vitrin_hashtags(content)
    price = content.get("price") or "توافقی"
    return (
        f"🟡 {html.escape(content.get('title') or 'آگهی ویترین')}\n\n"
        f"{hashtags}\n\n"
        f"📂 {html.escape(content.get('category') or '-')}\n"
        f"📍 {html.escape(content.get('city') or '-')}\n"
        f"💶 {html.escape(price)}\n\n"
        f"{SEPARATOR}\n\n"
        f"{html.escape(content.get('description') or '')}\n\n"
        f"{SEPARATOR}\n\n"
        f"🆔 {content['human_id']}\n"
        f"🦉 @{BOT_USERNAME}"
    )


def hayat_channel_text(content):
    city = content.get("city")
    city_line = f"\n📍 {html.escape(city)}\n" if city else "\n"
    return (
        "پیام ناشناس\n\n"
        "────────────────────\n\n"
        f"{html.escape(content.get('description') or '')}\n\n"
        "────────────────────\n"
        f"{city_line}"
        "نویسنده: ناشناس\n\n"
        f"{hayat_hashtags()}\n\n"
        f"🦉 @{BOT_USERNAME}"
    )


def channel_post_text(content):
    if content.get("content_type") == "hayat":
        return hayat_channel_text(content)
    return vitrin_channel_text(content)


def admin_content_text(content):
    if content.get("content_type") == "hayat":
        return (
            "📥 بررسی پیام حیاط خلوت\n\n"
            f"🆔 {content['human_id']}\n"
            "نوع: hayat\n"
            f"📍 شهر: {content.get('city') or 'ثبت نشده'}\n\n"
            f"{SEPARATOR}\n\n"
            f"{content.get('description') or '-'}"
        )

    media = "دارد" if content.get("media_file_id") else "ندارد"
    return (
        "📥 بررسی آگهی ویترین\n\n"
        f"🆔 {content['human_id']}\n"
        "نوع: vitrin\n"
        f"📂 دسته: {content.get('category') or '-'}\n"
        f"📍 شهر: {content.get('city') or '-'}\n"
        f"🏷 عنوان: {content.get('title') or '-'}\n"
        f"💶 قیمت: {content.get('price') or 'ثبت نشده'}\n"
        f"🖼 رسانه: {media}\n\n"
        f"{SEPARATOR}\n\n"
        f"{content.get('description') or '-'}"
    )


def draft_actions_keyboard(content):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ ادامه ویرایش", callback_data=f"draft:edit:{content['human_id']}")],
            [InlineKeyboardButton("👁 پیش‌نمایش", callback_data=f"draft:preview:{content['human_id']}")],
            [InlineKeyboardButton("📨 ارسال برای بررسی", callback_data=f"draft:submit:{content['human_id']}")],
            [InlineKeyboardButton("🗄 آرشیو", callback_data=f"draft:archive:{content['human_id']}")],
        ]
    )


def preview_keyboard(content):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ ویرایش", callback_data=f"draft:edit:{content['human_id']}")],
            [InlineKeyboardButton("🗄 حذف/آرشیو", callback_data=f"draft:archive:{content['human_id']}")],
            [InlineKeyboardButton("📨 ارسال برای بررسی", callback_data=f"draft:submit:{content['human_id']}")],
        ]
    )


def admin_review_keyboard(content_human_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Approve", callback_data=f"admin:approve:{content_human_id}")],
            [InlineKeyboardButton("↩️ Needs Edit", callback_data=f"admin:need_edit:{content_human_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"admin:reject:{content_human_id}")],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"admin:delete:{content_human_id}")],
        ]
    )


def published_keyboard(content_human_id):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 پسندیدم", callback_data=f"pub:like:{content_human_id}"),
                InlineKeyboardButton("👎 نپسندیدم", callback_data=f"pub:dislike:{content_human_id}"),
            ],
            [
                InlineKeyboardButton("💬 ثبت نظر", callback_data=f"pub:comment:{content_human_id}"),
                InlineKeyboardButton("مشاهده نظرات", callback_data=f"pub:comments:{content_human_id}"),
            ],
            [InlineKeyboardButton("🚩 گزارش", callback_data=f"pub:report:{content_human_id}")],
        ]
    )


def admin_comment_keyboard(comment_human_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ تایید نظر", callback_data=f"comment:approve:{comment_human_id}")],
            [InlineKeyboardButton("❌ رد نظر", callback_data=f"comment:reject:{comment_human_id}")],
        ]
    )
