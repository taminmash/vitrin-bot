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
    return "پیام حیاط خلوت" if is_hayat_content(content) else "آگهی ویترین"


def is_hayat_content(content):
    return content.get("content_type") in ("hayat", "hayat_message")


def content_preview_text(content):
    if is_hayat_content(content):
        city = content.get("city") or "ندارد"
        return (
            "پیش‌نمایش پیام ناشناس شما:\n\n"
            "🟣 حیاط خلوت اسپانیا\n\n"
            f"📍 شهر: {city}\n"
            f"💬 پیام: {content.get('description') or '-'}\n\n"
            "⚠️ نام، یوزرنیم، آیدی تلگرام و لینک پروفایل شما منتشر نمی‌شود."
        )

    return (
        "پیش‌نمایش آگهی شما:\n\n"
        "🟡 ویترین اسپانیا\n\n"
        f"📌 دسته‌بندی: {content.get('category') or '-'}\n"
        f"📍 شهر: {content.get('city') or '-'}\n"
        f"📝 توضیحات: {content.get('description') or '-'}"
    )


def vitrin_channel_text(content):
    return (
        "🟡 ویترین اسپانیا\n\n"
        f"📌 دسته‌بندی: {html.escape(content.get('category') or '-')}\n"
        f"📍 شهر: {html.escape(content.get('city') or '-')}\n"
        f"📝 توضیحات: {html.escape(content.get('description') or '')}\n\n"
        "شناسه آگهی:\n"
        f"{content['human_id']}"
    )


def hayat_channel_text(content):
    city = content.get("city") or "ندارد"
    return (
        "🟣 حیاط خلوت اسپانیا\n\n"
        f"📍 شهر: {html.escape(city)}\n"
        f"💬 پیام: {html.escape(content.get('description') or '')}\n\n"
        "شناسه پیام:\n"
        f"{content['human_id']}"
    )


def channel_post_text(content):
    if is_hayat_content(content):
        return hayat_channel_text(content)
    return vitrin_channel_text(content)


def admin_content_text(content):
    if is_hayat_content(content):
        return (
            "📥 بررسی پیام حیاط خلوت\n\n"
            f"🆔 {content['human_id']}\n"
            "نوع: hayat\n"
            f"📍 شهر: {content.get('city') or 'ثبت نشده'}\n\n"
            f"{SEPARATOR}\n\n"
            f"{content.get('description') or '-'}"
        )

    return (
        "📥 بررسی آگهی ویترین\n\n"
        f"🆔 {content['human_id']}\n"
        "نوع: vitrin\n"
        f"📂 دسته: {content.get('category') or '-'}\n"
        f"📍 شهر: {content.get('city') or '-'}\n\n"
        f"{SEPARATOR}\n\n"
        f"{content.get('description') or '-'}"
    )


def need_edit_text(content, reason):
    return (
        "✏️ درخواست ویرایش آگهی\n\n"
        f"{content_preview_text(content)}\n\n"
        f"{SEPARATOR}\n\n"
        "✏️ دلیل ویرایش:\n"
        f"{reason}"
    )


def need_edit_keyboard(content):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ ویرایش آگهی", callback_data=f"draft:edit:{content['human_id']}")],
            [InlineKeyboardButton("🗑 حذف آگهی", callback_data=f"draft:archive:{content['human_id']}")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data=f"draft:home:{content['human_id']}")],
        ]
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
            [InlineKeyboardButton("🗑 حذف", callback_data=f"draft:archive:{content['human_id']}")],
            [InlineKeyboardButton("📤 ارسال برای بررسی", callback_data=f"draft:submit:{content['human_id']}")],
            [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data=f"draft:home:{content['human_id']}")],
        ]
    )


def admin_review_keyboard(content_human_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ تأیید", callback_data=f"admin:approve:{content_human_id}")],
            [InlineKeyboardButton("↩️ درخواست اصلاح", callback_data=f"admin:need_edit:{content_human_id}")],
            [InlineKeyboardButton("❌ رد", callback_data=f"admin:reject:{content_human_id}")],
            [InlineKeyboardButton("🗑 حذف", callback_data=f"admin:delete:{content_human_id}")],
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
                InlineKeyboardButton("💬 مشاهده نظرات", callback_data=f"pub:comments:{content_human_id}"),
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
