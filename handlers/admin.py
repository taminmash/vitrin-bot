import logging
from datetime import datetime, timedelta

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import BadRequest, TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config_v2 import ADMIN_IDS, CHANNEL_HAYAT, CHANNEL_VITRIN, TECH_SUPPORT_IDS
from database.db import (
    create_radar_item,
    count_radar_reactions,
    get_comment,
    get_content,
    get_radar_item,
    list_active_reports,
    list_admin_radar_items,
    list_pending_comments,
    list_source_registry,
    list_pending_content,
    mark_radar_channel_failed,
    mark_radar_channel_published,
    resolve_comment,
    resolve_review,
    save_publication,
    submit_for_review,
    update_radar_content_status,
)
from handlers.common import (
    admin_comment_keyboard,
    admin_content_text,
    admin_review_keyboard,
    category_label,
    channel_post_text,
    published_keyboard,
    is_hayat_content,
    need_edit_keyboard,
    need_edit_text,
)
from handlers.radar import (
    channel_post_keyboard,
    format_radar_admin_preview,
    format_radar_channel_post,
    renderer_field_log,
)
from radar_engine.review.storage import (
    approve_candidate,
    load_review_queue,
    needs_edit_candidate,
    reject_candidate,
    review_status_report,
)
from radar_engine.review.presentation import build_review_item_text, build_review_queue_display
from radar_engine.promotion.storage import get_approved_promotion_source, promote_candidate


logger = logging.getLogger(__name__)


ADMIN_RADAR_MANAGE = "📡 مدیریت رادار"
ADMIN_PENDING = "📝 مدیریت محتواهای در انتظار"
ADMIN_COMMENTS = "💬 مدیریت کامنت‌ها"
ADMIN_REPORTS = "🚨 گزارش‌ها"
ADMIN_HOME = "🏠 بازگشت به خانه"
ADMIN_RADAR_BACK = "⬅️ بازگشت"
ADMIN_RADAR = "📡 انتشار رادار"
ADMIN_RADAR_NEW = "➕ محتوای جدید"
ADMIN_RADAR_DRAFTS = "📝 پیش‌نویس‌ها"
ADMIN_RADAR_READY = "✅ آماده انتشار"
ADMIN_RADAR_PUBLISHED = "📤 منتشرشده‌ها"
ADMIN_RADAR_FAILED = "❌ ناموفق‌ها"
ADMIN_RADAR_SOURCES = "📚 منابع رادار"
ADMIN_RADAR_REVIEW = "🧭 بازبینی رادار"
RADAR_STATUS_LABELS = {
    "draft": "پیش‌نویس",
    "ready": "آماده انتشار",
    "published": "منتشرشده",
    "expired": "منقضی",
    "failed": "ناموفق",
}
ADMIN_PANEL_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(ADMIN_RADAR_MANAGE)],
        [KeyboardButton(ADMIN_PENDING)],
        [KeyboardButton(ADMIN_COMMENTS)],
        [KeyboardButton(ADMIN_REPORTS)],
        [KeyboardButton(ADMIN_HOME)],
    ],
    resize_keyboard=True,
)

ADMIN_RADAR_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(ADMIN_RADAR_NEW)],
        [KeyboardButton(ADMIN_RADAR_DRAFTS)],
        [KeyboardButton(ADMIN_RADAR_READY)],
        [KeyboardButton(ADMIN_RADAR_PUBLISHED)],
        [KeyboardButton(ADMIN_RADAR_FAILED)],
        [KeyboardButton(ADMIN_RADAR_SOURCES)],
        [KeyboardButton(ADMIN_RADAR_REVIEW)],
        [KeyboardButton(ADMIN_RADAR_BACK)],
    ],
    resize_keyboard=True,
)

RADAR_CREATE_FIELDS = [
    ("title", "عنوان رادار را بفرستید:"),
    ("type", "دسته‌های رادار را انتخاب کنید:"),
    ("city", "محدوده را انتخاب کنید:"),
    ("summary", "خلاصه کوتاه را بفرستید:"),
    ("ai_reason", "چرا مهم است؟ یک توضیح کوتاه بفرستید:"),
    ("body", "جزئیات کامل را بفرستید:"),
    ("source_name", "نام منبع را بفرستید:"),
    ("source_url", "لینک منبع رسمی را بفرستید:"),
    ("start_date", "تاریخ شروع را انتخاب کنید:"),
    ("end_date", "مدت اعتبار را انتخاب کنید:"),
    ("urgency", "درجه فوریت را انتخاب کنید:"),
    ("audience_tags", "مخاطب مناسب را انتخاب کنید:"),
]

TYPE_CATEGORY = {
    "alert": "فوری",
    "discount": "تخفیف‌ها",
    "event": "ایونت‌ها",
    "job": "کار",
    "legal": "قوانین",
    "travel": "سفر",
    "family": "خانواده",
    "weather": "هوا",
    "transport": "حمل‌ونقل",
    "economy": "اقتصاد",
    "education": "آموزش",
}

RADAR_CATEGORY_OPTIONS = [
    ("alert", "🚨 هشدار"),
    ("discount", "💶 تخفیف"),
    ("event", "🎉 رویداد"),
    ("job", "💼 کار"),
    ("legal", "🏛 قانون"),
    ("travel", "✈️ سفر"),
    ("family", "👨‍👩‍👧 خانواده"),
    ("weather", "🌦 هوا"),
    ("transport", "🚇 حمل‌ونقل"),
    ("economy", "💰 اقتصاد"),
    ("education", "📚 آموزش"),
]

URGENCY_OPTIONS = [
    ("low", "🟢 کم"),
    ("medium", "🟡 معمولی"),
    ("high", "🟠 مهم"),
    ("urgent", "🔴 فوری"),
]

AUDIENCE_OPTIONS = [
    ("family", "👨‍👩‍👧 خانواده"),
    ("shopping", "🛍 خرید"),
    ("discount", "💶 تخفیف"),
    ("job_seeker", "💼 کارجو"),
    ("student", "🎓 دانشجو"),
    ("migration", "🛂 مهاجرت"),
    ("residency", "🏠 اقامت"),
    ("digital_nomad", "💻 دیجیتال نومد"),
    ("autonomo", "🧾 خوداشتغال"),
    ("business", "🏢 کسب‌وکار"),
    ("traveler", "✈️ مسافر"),
    ("all", "👥 همه"),
]

CITY_OPTIONS = [
    ("کل اسپانیا", "🇪🇸 کل اسپانیا"),
    ("Madrid", "Madrid"),
    ("Barcelona", "Barcelona"),
    ("Valencia", "Valencia"),
    ("Sevilla", "Sevilla"),
    ("Málaga", "Málaga"),
    ("Badajoz", "Badajoz"),
]

EDIT_FIELD_LABELS = [
    ("title", "عنوان"),
    ("type", "دسته‌ها"),
    ("city", "شهر"),
    ("summary", "خلاصه"),
    ("ai_reason", "چرا مهم است"),
    ("body", "جزئیات"),
    ("source_name", "نام منبع"),
    ("source_url", "لینک منبع"),
    ("start_date", "تاریخ شروع"),
    ("end_date", "تاریخ پایان"),
    ("urgency", "فوریت"),
    ("audience_tags", "مخاطب"),
]

SELECTOR_FIELDS = {"type", "city", "start_date", "end_date", "urgency", "audience_tags"}
TEXT_INPUT_FIELDS = {"title", "summary", "ai_reason", "body", "source_name", "source_url"}
STEP_LABELS = {
    "title": "عنوان",
    "type": "دسته‌ها",
    "city": "شهر/محدوده",
    "summary": "خلاصه کوتاه",
    "ai_reason": "چرا مهم است",
    "body": "جزئیات کامل",
    "source_name": "نام منبع",
    "source_url": "لینک منبع",
    "start_date": "تاریخ شروع",
    "end_date": "تاریخ پایان",
    "urgency": "فوریت",
    "audience_tags": "مخاطب",
}
TEXT_FIELD_PROMPTS = {
    "title": "عنوان مطلب را ارسال کنید.",
    "summary": "خلاصه کوتاه را ارسال کنید.",
    "ai_reason": "چرا مهم است؟ یک توضیح کوتاه ارسال کنید.",
    "body": "جزئیات کامل را ارسال کنید.",
    "source_name": "نام منبع را ارسال کنید.",
    "source_url": "لینک منبع رسمی را ارسال کنید.",
}


def clear_non_admin_flow_state(context):
    for key in (
        "profile_step",
        "post_step",
        "interaction_step",
        "interaction_content_id",
        "content_id",
        "flow",
    ):
        context.user_data.pop(key, None)


def stop_admin_update(reason):
    logger.debug("Stopping admin update propagation: %s", reason)
    raise ApplicationHandlerStop


def admin_panel_inline_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ADMIN_RADAR_MANAGE, callback_data="admin:panel:radar")],
            [InlineKeyboardButton(ADMIN_PENDING, callback_data="admin:panel:pending")],
            [InlineKeyboardButton(ADMIN_COMMENTS, callback_data="admin:panel:comments")],
            [InlineKeyboardButton(ADMIN_REPORTS, callback_data="admin:panel:reports")],
            [InlineKeyboardButton(ADMIN_HOME, callback_data="admin:panel:home")],
        ]
    )


def admin_radar_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ADMIN_RADAR_NEW, callback_data="admin_radar:menu:new")],
            [
                InlineKeyboardButton(ADMIN_RADAR_DRAFTS, callback_data="admin_radar:menu:draft"),
                InlineKeyboardButton(ADMIN_RADAR_READY, callback_data="admin_radar:menu:ready"),
            ],
            [
                InlineKeyboardButton(ADMIN_RADAR_PUBLISHED, callback_data="admin_radar:menu:published"),
                InlineKeyboardButton(ADMIN_RADAR_FAILED, callback_data="admin_radar:menu:failed"),
            ],
            [InlineKeyboardButton(ADMIN_RADAR_REVIEW, callback_data="admin_radar:review:list")],
            [InlineKeyboardButton(ADMIN_RADAR_SOURCES, callback_data="admin_radar:menu:sources")],
            [
                InlineKeyboardButton("⬅️ بازگشت به پنل ادمین", callback_data="admin_radar:menu:admin"),
                InlineKeyboardButton("🏠 خانه", callback_data="admin_radar:menu:home"),
            ],
        ]
    )


def step_progress_text(step_index):
    field, _ = RADAR_CREATE_FIELDS[step_index]
    total = len(RADAR_CREATE_FIELDS)
    label = STEP_LABELS.get(field, field)
    return f"مرحله {step_index + 1} از {total}\n{label}"


def step_prompt_text(step_index):
    field, default_prompt = RADAR_CREATE_FIELDS[step_index]
    prompt = TEXT_FIELD_PROMPTS.get(field, default_prompt)
    if step_index == 0:
        return f"📝 ساخت محتوای جدید رادار\n{step_progress_text(step_index)}\n\n{prompt}"
    return f"{step_progress_text(step_index)}\n\n{prompt}"


def create_nav_keyboard(include_back=True):
    rows = []
    if include_back:
        rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")])
    return InlineKeyboardMarkup(rows)


def validate_radar_text_field(field, text):
    value = (text or "").strip()
    if not value:
        return None, "این فیلد نمی‌تواند خالی باشد. لطفاً مقدار معتبر ارسال کنید."
    if field == "source_url" and not (value.startswith("http://") or value.startswith("https://")):
        return None, "لینک منبع باید با http:// یا https:// شروع شود."
    return value, None


def is_admin(user_id):
    return user_id in ADMIN_IDS or user_id in TECH_SUPPORT_IDS


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    await update.message.reply_text(
        "Who am I?\n\n"
        f"Telegram user ID: {user.id}\n"
        f"username: @{user.username or '-'}\n"
        f"is_admin: {'yes' if is_admin(user.id) else 'no'}"
    )


def radar_status(item):
    if item.get("channel_status") == "failed":
        return "failed"
    if is_radar_expired(item):
        return "expired"
    return item.get("content_status") or "draft"


def short_radar_title(item, limit=34):
    title = item.get("title") or "-"
    return title if len(title) <= limit else title[: limit - 1] + "…"


def parse_radar_date(value):
    from datetime import datetime, timedelta

    text = (value or "").strip()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if text in ("امروز", "today"):
        return today
    if text in ("7", "+7"):
        return today + timedelta(days=7)
    return datetime.strptime(text, "%Y-%m-%d")


def normalize_radar_type(value):
    text = (value or "").strip()
    aliases = {
        "فوری": "alert",
        "تخفیف": "discount",
        "تخفیف‌ها": "discount",
        "ایونت": "event",
        "ایونت‌ها": "event",
        "کار": "job",
        "قانون": "legal",
        "قوانین": "legal",
        "سفر": "travel",
        "خانواده": "family",
        "هوا": "weather",
        "حمل‌ونقل": "transport",
        "اقتصاد": "economy",
        "آموزش": "education",
    }
    return aliases.get(text, text if text in TYPE_CATEGORY else "alert")


def field_index(field):
    for index, (name, _) in enumerate(RADAR_CREATE_FIELDS):
        if name == field:
            return index
    return 0


def option_label(options, value):
    for option_value, label in options:
        if option_value == value:
            return label
    return value or "-"


def category_labels(values):
    return [option_label(RADAR_CATEGORY_OPTIONS, value) for value in values or []]


def audience_labels(values):
    return [option_label(AUDIENCE_OPTIONS, value) for value in values or []]


def urgency_label(value):
    return option_label(URGENCY_OPTIONS, value)


def normalize_audience_tags(tags):
    if not tags:
        return []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.replace("،", ",").split(",")]
    normalized = []
    for tag in tags:
        tag = str(tag).strip()
        if tag and tag not in normalized:
            normalized.append(tag)
    if "all" in normalized:
        return ["all"]
    return normalized


async def safe_edit_message_text(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as error:
        if "Message is not modified" in str(error):
            logger.info("Skipped unchanged Telegram edit for callback data=%r", query.data)
            return
        raise


def selector_keyboard(field, data):
    if field == "type":
        selected = data.get("category_tags") or ([data["type"]] if data.get("type") else [])
        rows = [
            [
                InlineKeyboardButton(
                    f"{'☑️' if value in selected else '☐'} {label}",
                    callback_data=f"admin_radar:cat:{value}",
                )
            ]
            for value, label in RADAR_CATEGORY_OPTIONS
        ]
        rows.append([InlineKeyboardButton("✅ تأیید", callback_data="admin_radar:cat_done")])
        rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")])
        rows.append([InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")])
        return InlineKeyboardMarkup(rows)

    if field == "city":
        rows = [[InlineKeyboardButton(label, callback_data=f"admin_radar:city:{value}")] for value, label in CITY_OPTIONS]
        rows.append([InlineKeyboardButton("📍 شهر دیگر", callback_data="admin_radar:city:other")])
        rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")])
        rows.append([InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")])
        return InlineKeyboardMarkup(rows)

    if field == "start_date":
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📅 امروز", callback_data="admin_radar:date:start:today")],
                [InlineKeyboardButton("📅 فردا", callback_data="admin_radar:date:start:tomorrow")],
                [InlineKeyboardButton("✍️ ورود تاریخ دستی", callback_data="admin_radar:date:start:manual")],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")],
                [InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")],
            ]
        )

    if field == "end_date":
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("1 روز", callback_data="admin_radar:date:end:1"),
                    InlineKeyboardButton("3 روز", callback_data="admin_radar:date:end:3"),
                ],
                [
                    InlineKeyboardButton("7 روز", callback_data="admin_radar:date:end:7"),
                    InlineKeyboardButton("14 روز", callback_data="admin_radar:date:end:14"),
                ],
                [InlineKeyboardButton("30 روز", callback_data="admin_radar:date:end:30")],
                [InlineKeyboardButton("✍️ ورود تاریخ دستی", callback_data="admin_radar:date:end:manual")],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")],
                [InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")],
            ]
        )

    if field == "urgency":
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, callback_data=f"admin_radar:urgency:{value}")] for value, label in URGENCY_OPTIONS]
            + [
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")],
                [InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")],
            ]
        )

    if field == "audience_tags":
        selected = normalize_audience_tags(data.get("audience_tags"))
        data["audience_tags"] = selected
        rows = [
            [
                InlineKeyboardButton(
                    f"{'☑️' if value in selected else '☐'} {label}",
                    callback_data=f"admin_radar:aud:{value}",
                )
            ]
            for value, label in AUDIENCE_OPTIONS
        ]
        rows.append([InlineKeyboardButton("✅ تأیید", callback_data="admin_radar:aud_done")])
        rows.append([InlineKeyboardButton("➕ افزودن تگ سفارشی", callback_data="admin_radar:aud_custom")])
        rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:create:back")])
        rows.append([InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")])
        return InlineKeyboardMarkup(rows)

    return None


def edit_field_keyboard():
    rows = [[InlineKeyboardButton(label, callback_data=f"admin_radar:edit_field:{field}")] for field, label in EDIT_FIELD_LABELS]
    rows.append([InlineKeyboardButton("بازگشت", callback_data="admin_radar:create:preview")])
    return InlineKeyboardMarkup(rows)


def today_midnight():
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def is_radar_expired(item):
    from datetime import datetime

    now = datetime.now()
    for key in ("expires_at", "end_date"):
        value = item.get(key)
        if value and value <= now:
            return True
    return (item.get("content_status") or "") == "expired"


def radar_create_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💾 ذخیره پیش‌نویس", callback_data="admin_radar:create:save_draft")],
            [InlineKeyboardButton("✅ آماده انتشار", callback_data="admin_radar:create:ready")],
            [InlineKeyboardButton("📤 انتشار در کانال", callback_data="admin_radar:create:publish")],
            [InlineKeyboardButton("✏️ ویرایش", callback_data="admin_radar:create:edit")],
            [InlineKeyboardButton("❌ انصراف", callback_data="admin_radar:create:cancel")],
        ]
    )


def radar_create_preview_text(data):
    item = {
        **data,
        "category": TYPE_CATEGORY.get(data.get("type"), data.get("category")),
        "source_name": data.get("source_name"),
    }
    categories = "، ".join(category_labels(data.get("category_tags") or [data.get("type")])) or "-"
    data["audience_tags"] = normalize_audience_tags(data.get("audience_tags"))
    audience = "، ".join(audience_labels(data.get("audience_tags") or [])) or "-"
    item.update(
        {
            "admin_categories": categories,
            "admin_audience": audience,
            "admin_urgency": urgency_label(data.get("urgency") or "low"),
            "admin_validity": f"{data.get('start_date') or '-'} تا {data.get('end_date') or '-'}",
            "admin_status": "پیش‌نویس در حال ساخت",
        }
    )
    logger.info("Rendering Radar create preview fields=%s", renderer_field_log(item))
    return "پیش‌نمایش محتوای رادار\n\n" + format_radar_admin_preview(item)


def radar_admin_item_preview_text(item):
    categories = "، ".join(category_labels(item.get("category_tags") or [item.get("type")])) or "-"
    audience = "، ".join(audience_labels(normalize_audience_tags(item.get("audience_tags")))) or "-"
    reactions = count_radar_reactions(item["id"])
    feedback_total = reactions.get("like", 0) + reactions.get("dislike", 0)
    preview_item = {
        **item,
        "admin_categories": categories,
        "admin_audience": audience,
        "admin_urgency": urgency_label(item.get("urgency") or "low"),
        "admin_validity": f"{item.get('start_date') or '-'} تا {item.get('end_date') or '-'}",
        "admin_status": radar_status(item),
    }
    logger.info("Rendering Radar admin item preview fields=%s", renderer_field_log(preview_item))
    return (
        f"{format_radar_admin_preview(preview_item)}\n\n"
        f"👍 پسندیدم: {reactions.get('like', 0)}\n"
        f"👎 نپسندیدم: {reactions.get('dislike', 0)}\n"
        f"📊 مجموع بازخورد: {feedback_total}"
    )


def create_payload_from_radar_data(data, status):
    radar_type = normalize_radar_type(data.get("type"))
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    return {
        "title": data.get("title"),
        "type": radar_type,
        "category": TYPE_CATEGORY.get(radar_type, radar_type),
        "category_tags": data.get("category_tags") or [radar_type],
        "city": data.get("city") or "کل اسپانیا",
        "province": data.get("province") or data.get("city") or "کل اسپانیا",
        "country": "Spain",
        "summary": data.get("summary"),
        "ai_reason": data.get("ai_reason"),
        "ai_summary": data.get("summary"),
        "body": data.get("body"),
        "source_name": data.get("source_name"),
        "source_url": data.get("source_url"),
        "start_date": start_date,
        "end_date": end_date,
        "expires_at": end_date,
        "urgency": data.get("urgency") or "low",
        "priority_score": {"urgent": 95, "high": 80, "medium": 55, "low": 30}.get(data.get("urgency"), 30),
        "audience_tags": normalize_audience_tags(data.get("audience_tags")),
        "ai_tags": normalize_audience_tags(data.get("audience_tags")),
        "original_text": data.get("body"),
        "original_language": "fa",
        "is_verified": True,
        "is_published": status in ("ready", "published"),
    }


async def publish_radar_item(context, item):
    logger.info("Publishing Radar channel post fields=%s", renderer_field_log(item))
    message = await context.bot.send_message(
        chat_id=CHANNEL_VITRIN,
        text=format_radar_channel_post(item),
        reply_markup=channel_post_keyboard(item),
        disable_web_page_preview=True,
    )
    return mark_radar_channel_published(item["id"], message.message_id)


def radar_admin_list_text(grouped_items):
    lines = ["📡 انتشار رادار اسپانیا", ""]
    for status, label in RADAR_STATUS_LABELS.items():
        items = grouped_items.get(status) or []
        lines.append(f"{label}: {len(items)}")
        if not items:
            lines.append("- موردی نیست")
            lines.append("")
            continue
        for item in items:
            lines.append(
                f"- {item.get('title') or '-'} | "
                f"{item.get('category') or item.get('type') or '-'} | "
                f"{item.get('urgency') or '-'} | "
                f"{item.get('city') or '-'} | "
                f"{radar_status(item)} / channel: {item.get('channel_status') or 'not_sent'}"
            )
        lines.append("")
    sources = list_source_registry()
    lines.append("منابع فعال:")
    lines.append(f"{len(sources)} منبع ثبت شده")
    if sources:
        lines.append("، ".join(source["name"] for source in sources[:8]))
    return "\n".join(lines).strip()


def radar_admin_list_keyboard(grouped_items):
    rows = []
    for status, label in RADAR_STATUS_LABELS.items():
        for item in grouped_items.get(status) or []:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{label}: {short_radar_title(item)}",
                        callback_data=f"admin_radar:item:{item['id']}",
                    )
                ]
            )
    rows.append([InlineKeyboardButton("🔄 تازه‌سازی", callback_data="admin_radar:list")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت به مدیریت رادار", callback_data="admin_radar:menu:open")])
    return InlineKeyboardMarkup(rows)


def radar_item_preview_keyboard(item):
    rows = []
    if radar_status(item) != "published":
        rows.append([InlineKeyboardButton("📤 انتشار در کانال", callback_data=f"admin_radar:publish:{item['id']}")])
    elif item.get("channel_message_id"):
        rows.append(
            [InlineKeyboardButton("🔄 بروزرسانی دکمه‌های کانال", callback_data=f"admin_radar:refresh_buttons:{item['id']}")]
        )
    rows.append([InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")])
    return InlineKeyboardMarkup(rows)


def radar_review_queue_text(items):
    text, _ = radar_review_queue_payload(items)
    return text


def radar_review_queue_payload(items):
    return build_review_queue_display(items, review_status_report())


def radar_review_queue_keyboard(items):
    rows = [
        [
            InlineKeyboardButton(
                short_radar_title({"title": item.candidate.title}),
                callback_data=f"admin_radar:review:item:{item.candidate_id}",
            )
        ]
        for item in items
    ]
    rows.append([InlineKeyboardButton("🔄 تازه‌سازی", callback_data="admin_radar:review:list")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت به مدیریت رادار", callback_data="admin_radar:menu:open")])
    return InlineKeyboardMarkup(rows)


def radar_review_item_text(item):
    return build_review_item_text(
        item,
        category_labeler=category_labels,
        audience_labeler=audience_labels,
        urgency_labeler=urgency_label,
    )


def radar_review_item_keyboard(candidate_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ تأیید", callback_data=f"admin_radar:review:approve:{candidate_id}")],
            [InlineKeyboardButton("❌ رد", callback_data=f"admin_radar:review:reject:{candidate_id}")],
            [InlineKeyboardButton("✏️ نیازمند ویرایش", callback_data=f"admin_radar:review:needs_edit:{candidate_id}")],
            [InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")],
        ]
    )


def radar_promotion_keyboard(candidate_id=None):
    rows = []
    if candidate_id:
        rows.append(
            [InlineKeyboardButton("آماده‌سازی برای انتشار", callback_data=f"admin_radar:promote:{candidate_id}")]
        )
    rows.append([InlineKeyboardButton("✅ آماده انتشارها", callback_data="admin_radar:menu:ready")])
    rows.append([InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")])
    return InlineKeyboardMarkup(rows)


async def edit_admin_radar_review_queue(query):
    items = load_review_queue(limit=20)
    text, visible_items = radar_review_queue_payload(items)
    await query.edit_message_text(
        text,
        reply_markup=radar_review_queue_keyboard(visible_items),
        disable_web_page_preview=True,
    )


async def send_admin_radar_list(message, only_status=None):
    grouped = list_admin_radar_items()
    if only_status:
        grouped = {status: items if status == only_status else [] for status, items in grouped.items()}
    await message.reply_text(
        radar_admin_list_text(grouped),
        reply_markup=radar_admin_list_keyboard(grouped),
    )


async def send_admin_radar_menu(message, remove_keyboard=True):
    if remove_keyboard:
        await message.reply_text("منوی رادار باز شد.", reply_markup=ReplyKeyboardRemove())
    await message.reply_text(
        "📡 مدیریت رادار\n\n"
        "یکی از بخش‌های زیر را انتخاب کنید:",
        reply_markup=admin_radar_menu_keyboard(),
    )


async def edit_admin_radar_menu(query):
    await query.edit_message_text(
        "📡 مدیریت رادار\n\n"
        "یکی از بخش‌های زیر را انتخاب کنید:",
        reply_markup=admin_radar_menu_keyboard(),
    )


async def send_admin_radar_sources(message):
    sources = list_source_registry()
    if not sources:
        await message.reply_text("منبع فعالی برای رادار ثبت نشده است.", reply_markup=admin_radar_menu_keyboard())
        return

    lines = ["📚 منابع رادار", ""]
    current_category = None
    for source in sources:
        category = source.get("category") or "Other"
        if category != current_category:
            current_category = category
            lines.extend(["", f"• {category}"])
        active = "فعال" if source.get("is_active") else "غیرفعال"
        lines.append(
            f"- {source.get('name') or '-'} | {source.get('source_type') or '-'} | "
            f"اعتماد: {source.get('trust_level') or '-'} | {active}"
        )

    await message.reply_text("\n".join(lines).strip(), reply_markup=admin_radar_menu_keyboard())


async def send_pending_comments(message):
    comments = list_pending_comments()
    if not comments:
        await message.reply_text("کامنتی در انتظار بررسی وجود ندارد.", reply_markup=admin_panel_inline_keyboard())
        return

    for comment in comments:
        await message.reply_text(
            "💬 مدیریت کامنت‌ها\n\n"
            f"🆔 {comment['human_id']}\n"
            f"محتوا: {comment.get('content_human_id') or '-'}\n\n"
            f"{comment.get('body') or '-'}",
            reply_markup=admin_comment_keyboard(comment["human_id"]),
        )


async def send_radar_step_prompt(message, state):
    step = state.get("step", 0)
    logger.info("Radar create prompt step=%s data_keys=%s", step, sorted((state.get("data") or {}).keys()))
    if step >= len(RADAR_CREATE_FIELDS):
        logger.info("Radar create reached preview step=%s", step)
        await message.reply_text(radar_create_preview_text(state.get("data") or {}), reply_markup=radar_create_keyboard())
        return

    field, prompt = RADAR_CREATE_FIELDS[step]
    keyboard = selector_keyboard(field, state.setdefault("data", {}))
    logger.info("Radar create sending field=%s selector=%s", field, bool(keyboard))
    await message.reply_text(step_prompt_text(step), reply_markup=keyboard or create_nav_keyboard(step > 0))


async def edit_radar_step_prompt(query, state):
    step = state.get("step", 0)
    field, _ = RADAR_CREATE_FIELDS[step]
    keyboard = selector_keyboard(field, state.setdefault("data", {}))
    logger.info("Radar create edit prompt step=%s field=%s selector=%s", step, field, bool(keyboard))
    await safe_edit_message_text(query, step_prompt_text(step), reply_markup=keyboard or create_nav_keyboard(step > 0))


async def finish_radar_field(message, state):
    if state.pop("editing_field", None):
        state["step"] = len(RADAR_CREATE_FIELDS)
        logger.info("Radar create finished edited field; returning to preview")
        await message.reply_text(radar_create_preview_text(state.get("data") or {}), reply_markup=radar_create_keyboard())
        return

    state["step"] = state.get("step", 0) + 1
    logger.info("Radar create advanced to step=%s", state["step"])
    await send_radar_step_prompt(message, state)


async def finish_radar_field_from_query(query, state):
    if state.pop("editing_field", None):
        state["step"] = len(RADAR_CREATE_FIELDS)
        logger.info("Radar create callback finished edited field; returning to preview")
        await query.edit_message_text(radar_create_preview_text(state.get("data") or {}), reply_markup=radar_create_keyboard())
        return

    state["step"] = state.get("step", 0) + 1
    step = state.get("step", 0)
    logger.info("Radar create callback advanced to step=%s", step)
    if step >= len(RADAR_CREATE_FIELDS):
        logger.info("Radar create callback reached preview step=%s", step)
        await query.edit_message_text(radar_create_preview_text(state.get("data") or {}), reply_markup=radar_create_keyboard())
        return

    await edit_radar_step_prompt(query, state)


async def start_radar_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_non_admin_flow_state(context)
    context.user_data["radar_create"] = {"step": 0, "data": {}}
    context.user_data["admin_radar_menu"] = True
    logger.info("Entering Radar new content flow user_id=%s", update.effective_user.id if update.effective_user else None)
    await update.message.reply_text("در حال ساخت محتوای جدید...", reply_markup=ReplyKeyboardRemove())
    await send_radar_step_prompt(update.message, context.user_data["radar_create"])


async def handle_radar_creation_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("radar_create")
    if not state:
        return False

    text = update.message.text.strip()
    logger.info("Radar create message step=%s text=%r", state.get("step"), text)
    if text in (ADMIN_RADAR_BACK, ADMIN_HOME):
        context.user_data.pop("radar_create", None)
        logger.info("Radar create cancelled by text=%r", text)
        await update.message.reply_text("ایجاد محتوای رادار لغو شد.", reply_markup=admin_radar_menu_keyboard())
        return True

    step = state.get("step", 0)
    if step >= len(RADAR_CREATE_FIELDS):
        await update.message.reply_text(
            "پیش‌نمایش آماده است. لطفاً یکی از دکمه‌های زیر را انتخاب کنید.",
            reply_markup=radar_create_keyboard(),
        )
        return True

    field, _ = RADAR_CREATE_FIELDS[step]
    data = state.setdefault("data", {})
    logger.info("Radar create handling field=%s", field)

    try:
        if state.pop("awaiting_custom_city", False):
            value, error = validate_radar_text_field("city", text)
            if error:
                await update.message.reply_text(error, reply_markup=create_nav_keyboard(True))
                return True
            data["city"] = value
            data["province"] = value
            logger.info("Radar create stored custom city=%r", text)
            await finish_radar_field(update.message, state)
            return True
        if state.pop("awaiting_manual_date", False):
            data[field] = parse_radar_date(text)
            if field == "end_date":
                data["expires_at"] = data[field]
            logger.info("Radar create stored manual date field=%s value=%s", field, data[field])
            await finish_radar_field(update.message, state)
            return True
        if state.pop("awaiting_custom_audience", False):
            value, error = validate_radar_text_field("audience_tags", text)
            if error:
                await update.message.reply_text(error, reply_markup=create_nav_keyboard(True))
                return True
            tags = normalize_audience_tags(data.get("audience_tags"))
            if "all" not in tags and value not in tags:
                tags.append(value)
            data["audience_tags"] = normalize_audience_tags(tags)
            logger.info("Radar create added custom audience tag=%r tags=%s", value, tags)
            await update.message.reply_text(
                "تگ سفارشی اضافه شد. انتخاب مخاطب را ادامه دهید یا تأیید کنید.",
                reply_markup=selector_keyboard("audience_tags", data),
            )
            return True

        if field in SELECTOR_FIELDS:
            logger.info("Radar create received text for selector field=%s; asking for button use", field)
            await update.message.reply_text("لطفاً از دکمه‌های همین مرحله استفاده کنید.")
            return True
        if field in TEXT_INPUT_FIELDS:
            value, error = validate_radar_text_field(field, text)
            if error:
                await update.message.reply_text(error, reply_markup=create_nav_keyboard(step > 0))
                return True
            data[field] = value
            logger.info("Radar create stored text field=%s", field)
            await finish_radar_field(update.message, state)
            return True
        if field == "type":
            radar_type = normalize_radar_type(text)
            data["type"] = radar_type
            data["category"] = TYPE_CATEGORY.get(radar_type, radar_type)
        elif field in ("start_date", "end_date"):
            data[field] = parse_radar_date(text)
        elif field == "urgency":
            data[field] = text if text in ("low", "medium", "high", "urgent") else "low"
        elif field == "audience_tags":
            data[field] = normalize_audience_tags(text)
        else:
            data[field] = text
        logger.info("Radar create stored field=%s", field)
    except Exception:
        logger.exception("Radar create failed to parse field=%s", field)
        await update.message.reply_text("فرمت این مقدار درست نیست. لطفاً دوباره بفرستید.")
        return True

    await finish_radar_field(update.message, state)
    return True


async def edit_admin_radar_list(query, only_status=None):
    grouped = list_admin_radar_items()
    if only_status:
        grouped = {status: items if status == only_status else [] for status, items in grouped.items()}
    await query.edit_message_text(
        radar_admin_list_text(grouped),
        reply_markup=radar_admin_list_keyboard(grouped),
    )


async def admin_radar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    logger.info(
        "Admin Radar callback user_id=%s data=%r radar_create=%s",
        query.from_user.id if query.from_user else None,
        query.data,
        bool(context.user_data.get("radar_create")),
    )
    if not is_admin(query.from_user.id):
        logger.warning("Non-admin attempted admin Radar callback user_id=%s data=%r", query.from_user.id, query.data)
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else "list"
    state = context.user_data.get("radar_create")
    logger.info("Admin Radar callback action=%s parts=%s state_step=%s", action, parts, state.get("step") if state else None)

    if action == "menu":
        operation = parts[2] if len(parts) > 2 else ""
        if operation == "new":
            clear_non_admin_flow_state(context)
            context.user_data["radar_create"] = {"step": 0, "data": {}}
            context.user_data["admin_radar_menu"] = True
            logger.info("Entering Radar new content flow from inline menu user_id=%s", query.from_user.id)
            await query.message.reply_text("در حال ساخت محتوای جدید...", reply_markup=ReplyKeyboardRemove())
            await send_radar_step_prompt(query.message, context.user_data["radar_create"])
            return
        if operation in ("draft", "ready", "published", "failed"):
            await edit_admin_radar_list(query, operation)
            return
        if operation == "sources":
            sources = list_source_registry()
            if not sources:
                await query.edit_message_text(
                    "منبع فعالی برای رادار ثبت نشده است.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:menu:open")]]
                    ),
                )
                return
            lines = ["📚 منابع رادار", ""]
            current_category = None
            for source in sources:
                category = source.get("category") or "Other"
                if category != current_category:
                    current_category = category
                    lines.extend(["", f"• {category}"])
                active = "فعال" if source.get("is_active") else "غیرفعال"
                lines.append(
                    f"- {source.get('name') or '-'} | {source.get('source_type') or '-'} | "
                    f"اعتماد: {source.get('trust_level') or '-'} | {active}"
                )
            await query.edit_message_text(
                "\n".join(lines).strip(),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_radar:menu:open")]]
                ),
            )
            return
        if operation == "admin":
            context.user_data.pop("admin_radar_menu", None)
            context.user_data.pop("radar_create", None)
            await query.edit_message_text("👨‍💼 پنل ادمین ویترین", reply_markup=admin_panel_inline_keyboard())
            return
        if operation == "home":
            context.user_data.clear()
            from handlers.start import MAIN_MENU

            await query.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
            await query.edit_message_reply_markup(reply_markup=None)
            return
        await edit_admin_radar_menu(query)
        return

    if action == "review":
        operation = parts[2] if len(parts) > 2 else "list"
        candidate_id = parts[3] if len(parts) > 3 else None
        if operation == "list":
            await edit_admin_radar_review_queue(query)
            return
        if operation == "item" and candidate_id:
            items = load_review_queue(limit=1, candidate_id=candidate_id)
            if not items:
                await query.edit_message_text(
                    "این گزینه برای بازبینی پیدا نشد یا قبلاً تصمیم‌گیری شده است.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")]]
                    ),
                )
                return
            await query.edit_message_text(
                radar_review_item_text(items[0]),
                reply_markup=radar_review_item_keyboard(candidate_id),
                disable_web_page_preview=True,
            )
            return
        if operation in ("approve", "reject", "needs_edit") and candidate_id:
            note = "Telegram admin Radar review"
            if operation == "approve":
                stored = approve_candidate(candidate_id, query.from_user.id, note)
                label = "تأیید شد"
                reply_markup = radar_promotion_keyboard(candidate_id)
            elif operation == "reject":
                stored = reject_candidate(candidate_id, query.from_user.id, note)
                label = "رد شد"
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")]]
                )
            else:
                stored = needs_edit_candidate(candidate_id, query.from_user.id, note)
                label = "نیازمند ویرایش شد"
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")]]
                )
            if not stored:
                await query.edit_message_text(
                    "برای این گزینه قبلاً تصمیم ثبت شده است.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")]]
                    ),
                )
                return
            await query.edit_message_text(
                f"✅ تصمیم بازبینی ثبت شد: {label}",
                reply_markup=reply_markup,
            )
            return
        await query.edit_message_text(
            "درخواست بازبینی معتبر نیست.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ بازگشت به بازبینی", callback_data="admin_radar:review:list")]]
            ),
        )
        return

    if action == "promote":
        candidate_id = parts[2] if len(parts) > 2 else None
        if not candidate_id:
            await query.edit_message_text(
                "درخواست آماده‌سازی معتبر نیست.",
                reply_markup=radar_promotion_keyboard(),
            )
            return
        source = get_approved_promotion_source(candidate_id)
        if not source:
            await query.edit_message_text(
                "این گزینه برای آماده‌سازی پیدا نشد یا هنوز تأیید نشده است.",
                reply_markup=radar_promotion_keyboard(),
            )
            return
        result = promote_candidate(source, promoted_by=query.from_user.id)
        if result.created:
            await query.edit_message_text(
                "✅ محتوای رادار با وضعیت آماده انتشار ساخته شد.\n\n"
                f"Radar item ID: {result.radar_item_id}",
                reply_markup=radar_promotion_keyboard(),
            )
            return
        if result.already_promoted:
            await query.edit_message_text(
                "این گزینه قبلاً آماده‌سازی شده است و نسخه تکراری ساخته نشد.\n\n"
                f"Radar item ID: {result.radar_item_id or '-'}",
                reply_markup=radar_promotion_keyboard(),
            )
            return
        await query.edit_message_text(
            "آماده‌سازی انجام نشد؛ داده‌های این گزینه برای ساخت آیتم رادار کامل نیست.",
            reply_markup=radar_promotion_keyboard(),
        )
        return

    if action in ("cat", "cat_done", "aud", "aud_done", "aud_custom", "city", "date", "urgency", "edit_field"):
        if not state:
            logger.warning("Admin Radar selector callback without active draft action=%s data=%r", action, query.data)
            await query.edit_message_text("پیش‌نویس فعالی برای رادار وجود ندارد.")
            return

        data = state.setdefault("data", {})

        if action == "cat":
            value = parts[2]
            selected = data.get("category_tags") or []
            if value in selected:
                selected.remove(value)
            else:
                selected.append(value)
            data["category_tags"] = selected
            await query.edit_message_text(RADAR_CREATE_FIELDS[field_index("type")][1], reply_markup=selector_keyboard("type", data))
            return

        if action == "cat_done":
            selected = data.get("category_tags") or []
            if not selected:
                await query.answer("حداقل یک دسته را انتخاب کنید.", show_alert=True)
                return
            primary_type = selected[0]
            data["type"] = primary_type
            data["category"] = TYPE_CATEGORY.get(primary_type, primary_type)
            await finish_radar_field_from_query(query, state)
            return

        if action == "aud":
            try:
                value = parts[2]
                selected = normalize_audience_tags(data.get("audience_tags"))
                if value == "all":
                    selected = ["all"]
                    await query.answer("گزینه «همه» انتخاب شد و بقیه مخاطب‌ها پاک شدند.")
                else:
                    if "all" in selected:
                        selected = []
                        await query.answer("برای انتخاب مخاطب خاص، گزینه «همه» پاک شد.")
                    if value in selected:
                        selected.remove(value)
                    else:
                        selected.append(value)
                data["audience_tags"] = normalize_audience_tags(selected)
                await safe_edit_message_text(
                    query,
                    RADAR_CREATE_FIELDS[field_index("audience_tags")][1],
                    reply_markup=selector_keyboard("audience_tags", data),
                )
            except Exception:
                logger.exception("Radar audience selector failed data=%s callback=%r", data, query.data)
                await query.answer("انتخاب مخاطب ثبت نشد. لطفاً دوباره یکی از گزینه‌ها را بزنید.", show_alert=True)
            return

        if action == "aud_done":
            try:
                data["audience_tags"] = normalize_audience_tags(data.get("audience_tags")) or ["all"]
                await finish_radar_field_from_query(query, state)
            except Exception:
                logger.exception("Radar audience confirmation failed data=%s callback=%r", data, query.data)
                await query.answer("مخاطب انتخاب‌شده معتبر نیست. لطفاً دوباره انتخاب کنید.", show_alert=True)
            return

        if action == "aud_custom":
            if normalize_audience_tags(data.get("audience_tags")) == ["all"]:
                data["audience_tags"] = []
                await query.answer("برای افزودن تگ سفارشی، گزینه «همه» پاک شد.")
            state["awaiting_custom_audience"] = True
            await safe_edit_message_text(
                query,
                f"{step_progress_text(state.get('step', field_index('audience_tags')))}\n\nتگ سفارشی مخاطب را ارسال کنید.",
                reply_markup=create_nav_keyboard(True),
            )
            return

        if action == "city":
            value = parts[2]
            if value == "other":
                state["awaiting_custom_city"] = True
                await safe_edit_message_text(
                    query,
                    f"{step_progress_text(state.get('step', field_index('city')))}\n\nنام شهر را ارسال کنید.",
                    reply_markup=create_nav_keyboard(True),
                )
                return
            data["city"] = value
            data["province"] = value
            await finish_radar_field_from_query(query, state)
            return

        if action == "date":
            date_field = "start_date" if parts[2] == "start" else "end_date"
            state["step"] = field_index(date_field)
            value = parts[3] if len(parts) > 3 else "manual"
            if value == "manual":
                state["awaiting_manual_date"] = True
                await safe_edit_message_text(
                    query,
                    f"{step_progress_text(state.get('step', field_index(date_field)))}\n\nتاریخ را با فرمت YYYY-MM-DD ارسال کنید.",
                    reply_markup=create_nav_keyboard(True),
                )
                return
            if date_field == "start_date":
                data[date_field] = today_midnight() + timedelta(days=1 if value == "tomorrow" else 0)
            else:
                base_date = data.get("start_date") or today_midnight()
                data[date_field] = base_date + timedelta(days=int(value))
                data["expires_at"] = data[date_field]
            await finish_radar_field_from_query(query, state)
            return

        if action == "urgency":
            value = parts[2]
            data["urgency"] = value if value in {"low", "medium", "high", "urgent"} else "low"
            await finish_radar_field_from_query(query, state)
            return

        if action == "edit_field":
            field = parts[2]
            if field not in {name for name, _ in RADAR_CREATE_FIELDS}:
                await query.edit_message_text("فیلد انتخاب‌شده معتبر نیست.")
                return
            state["step"] = field_index(field)
            state["editing_field"] = True
            await edit_radar_step_prompt(query, state)
            return

    if action == "back":
        await edit_admin_radar_menu(query)
        return

    if action == "list":
        await edit_admin_radar_list(query)
        return

    if action == "create":
        operation = parts[2] if len(parts) > 2 else ""
        data = context.user_data.get("radar_create", {}).get("data")
        if operation == "back":
            if not state:
                await edit_admin_radar_menu(query)
                return
            state.pop("awaiting_custom_city", None)
            state.pop("awaiting_manual_date", None)
            state.pop("awaiting_custom_audience", None)
            if state.get("editing_field"):
                state.pop("editing_field", None)
                state["step"] = len(RADAR_CREATE_FIELDS)
                await query.edit_message_text(radar_create_preview_text(state.get("data") or {}), reply_markup=radar_create_keyboard())
                return
            step = max(0, state.get("step", 0) - 1)
            state["step"] = step
            await edit_radar_step_prompt(query, state)
            return
        if operation == "new":
            clear_non_admin_flow_state(context)
            context.user_data["radar_create"] = {"step": 0, "data": {}}
            context.user_data["admin_radar_menu"] = True
            logger.info("Entering Radar new content flow from callback user_id=%s", query.from_user.id)
            await send_radar_step_prompt(query.message, context.user_data["radar_create"])
            return
        if operation == "cancel":
            context.user_data.pop("radar_create", None)
            context.user_data["admin_radar_menu"] = True
            await query.edit_message_text("ایجاد محتوای رادار لغو شد.")
            await query.message.reply_text(
                "📡 مدیریت رادار\n\n"
                "یکی از بخش‌های زیر را انتخاب کنید:",
                reply_markup=admin_radar_menu_keyboard(),
            )
            return
        if operation == "edit":
            if not data:
                await query.edit_message_text("پیش‌نویسی برای ویرایش وجود ندارد.")
                return
            await query.edit_message_text("کدام بخش را ویرایش می‌کنید؟", reply_markup=edit_field_keyboard())
            return
        if operation == "preview":
            if not data:
                await query.edit_message_text("پیش‌نویسی برای نمایش وجود ندارد.")
                return
            await query.edit_message_text(radar_create_preview_text(data), reply_markup=radar_create_keyboard())
            return
        if operation in ("save_draft", "ready", "publish"):
            if not data:
                await query.edit_message_text("اطلاعات محتوای رادار کامل نیست.")
                return
            status = "ready" if operation in ("ready", "publish") else "draft"
            item = create_radar_item(create_payload_from_radar_data(data, status), content_status=status)
            context.user_data.pop("radar_create", None)
            if operation != "publish":
                label = "آماده انتشار" if operation == "ready" else "پیش‌نویس"
                await query.edit_message_text(f"✅ محتوای رادار با وضعیت {label} ذخیره شد.")
                return
            if is_radar_expired(item):
                await query.edit_message_text("این آیتم منقضی شده و قابل انتشار نیست.")
                return
            try:
                published = await publish_radar_item(context, item)
            except TelegramError as error:
                logging.exception("Failed to publish new Radar item to channel")
                mark_radar_channel_failed(item["id"], str(error))
                await query.edit_message_text(f"❌ انتشار رادار در کانال ناموفق بود.\n\nخطا: {error}")
                return
            await query.edit_message_text(
                "✅ آیتم رادار در کانال منتشر شد.\n\n"
                f"Message ID: {published.get('channel_message_id') or '-'}"
            )
            return

    if len(parts) != 3:
        await query.edit_message_text("درخواست رادار نامعتبر است.")
        return

    item_id = parts[2]
    item = get_radar_item(item_id)
    if not item:
        await query.edit_message_text("آیتم رادار پیدا نشد.")
        return

    if action == "item":
        preview = radar_admin_item_preview_text(item)
        await query.edit_message_text(
            preview,
            reply_markup=radar_item_preview_keyboard(item),
            disable_web_page_preview=True,
        )
        return

    if action == "refresh_buttons":
        if not item.get("channel_message_id"):
            await query.edit_message_text(
                "برای این آیتم پیام کانال ثبت نشده است.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
                ),
            )
            return
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=CHANNEL_VITRIN,
                message_id=item["channel_message_id"],
                reply_markup=channel_post_keyboard(item),
            )
        except Exception as error:
            logging.exception("Failed to refresh Radar channel buttons")
            await query.edit_message_text(
                "❌ بروزرسانی دکمه‌های کانال ناموفق بود.\n\n"
                f"خطا: {error}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
                ),
            )
            return
        await query.edit_message_text(
            "✅ دکمه‌های کانال بروزرسانی شد.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
            ),
        )
        return

    if action == "publish":
        if radar_status(item) == "expired":
            await query.edit_message_text(
                "این آیتم منقضی شده و قابل انتشار نیست.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
                ),
            )
            return
        if item.get("channel_status") == "published":
            await query.edit_message_text(
                "این آیتم قبلاً منتشر شده است.\n\n"
                f"Message ID: {item.get('channel_message_id') or '-'}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
                ),
            )
            return
        update_radar_content_status(item_id, "ready")
        item = get_radar_item(item_id)
        try:
            published = await publish_radar_item(context, item)
        except TelegramError as error:
            logging.exception("Failed to publish Radar item %s to channel", item_id)
            mark_radar_channel_failed(item_id, str(error))
            await query.edit_message_text(
                "❌ انتشار رادار در کانال ناموفق بود.\n\n"
                f"خطا: {error}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
                ),
            )
            return

        await query.edit_message_text(
            "✅ آیتم رادار در کانال منتشر شد.\n\n"
            f"Message ID: {published.get('channel_message_id') or '-'}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")]]
            ),
        )


async def send_content_to_admin(context: ContextTypes.DEFAULT_TYPE, content):
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=admin_content_text(content),
            reply_markup=admin_review_keyboard(content["human_id"]),
        )


async def submit_content_to_admin(context: ContextTypes.DEFAULT_TYPE, content_human_id):
    content, _ = submit_for_review(content_human_id)
    await send_content_to_admin(context, content)
    return content


async def send_comment_to_admin(context: ContextTypes.DEFAULT_TYPE, comment):
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                "💬 نظر جدید برای بررسی\n\n"
                f"🆔 {comment['human_id']}\n"
                f"محتوا: {comment.get('content_human_id') or '-'}\n\n"
                f"{comment['body']}"
            ),
            reply_markup=admin_comment_keyboard(comment["human_id"]),
        )


async def publish_content(context: ContextTypes.DEFAULT_TYPE, content):
    channel_id = CHANNEL_HAYAT if is_hayat_content(content) else CHANNEL_VITRIN
    kwargs = {
        "chat_id": channel_id,
        "caption" if content.get("media_file_id") else "text": channel_post_text(content),
        "parse_mode": "HTML",
        "reply_markup": published_keyboard(content["human_id"]),
    }

    if content.get("media_file_id") and content.get("media_type") == "photo":
        msg = await context.bot.send_photo(photo=content["media_file_id"], **kwargs)
    elif content.get("media_file_id") and content.get("media_type") == "video":
        msg = await context.bot.send_video(video=content["media_file_id"], **kwargs)
    else:
        msg = await context.bot.send_message(**kwargs)

    save_publication(content["human_id"], channel_id, msg.message_id)
    return msg


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, action, object_id = parts

    if action == "panel":
        if object_id == "radar":
            clear_non_admin_flow_state(context)
            context.user_data["admin_panel"] = True
            context.user_data["admin_radar_menu"] = True
            await query.edit_message_text(
                "📡 مدیریت رادار\n\n"
                "یکی از بخش‌های زیر را انتخاب کنید:",
                reply_markup=admin_radar_menu_keyboard(),
            )
            return
        if object_id == "pending":
            pending = list_pending_content()
            await query.edit_message_text("📝 مدیریت محتواهای در انتظار")
            if not pending:
                await query.message.reply_text("موردی در انتظار بررسی وجود ندارد.", reply_markup=admin_panel_inline_keyboard())
                return
            for content in pending:
                await query.message.reply_text(
                    admin_content_text(content),
                    reply_markup=admin_review_keyboard(content["human_id"]),
                )
            return
        if object_id == "comments":
            await query.edit_message_text("💬 مدیریت کامنت‌ها")
            await send_pending_comments(query.message)
            return
        if object_id == "reports":
            reports = list_active_reports()
            if reports:
                text = "🚨 گزارش‌های فعال\n\n" + "\n".join(
                    f"{report['human_id']} برای {report['content_human_id']}: {report['reason']}"
                    for report in reports
                )
            else:
                text = "گزارش فعالی وجود ندارد."
            await query.edit_message_text(text, reply_markup=admin_panel_inline_keyboard())
            return
        if object_id == "home":
            context.user_data.clear()
            from handlers.start import MAIN_MENU

            await query.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
            await query.edit_message_reply_markup(reply_markup=None)
            return
        await query.edit_message_text("درخواست پنل ادمین معتبر نیست.", reply_markup=admin_panel_inline_keyboard())
        return

    if action == "approve":
        content = get_content(object_id)
        if not content or content["status"] != "pending_review":
            await query.edit_message_text("این محتوا دیگر در وضعیت بررسی نیست.")
            return

        await publish_content(context, content)
        resolve_review(object_id, query.from_user.id, "approve")
        label = "پیام" if is_hayat_content(content) else "آگهی"
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=f"✅ {label} شما تایید و منتشر شد.\n\n🆔 {content['human_id']}",
        )
        await query.edit_message_text(f"✅ منتشر شد: {content['human_id']}")
        return

    if action in ("need_edit", "reject", "delete"):
        content = get_content(object_id)
        if not content:
            await query.edit_message_text("❌ محتوا پیدا نشد.")
            return

        context.user_data["admin_reason_action"] = action
        context.user_data["admin_reason_content_id"] = object_id
        prompt = {
            "need_edit": "📝 دلیل نیاز به ویرایش را ارسال کنید:",
            "reject": "📝 دلیل رد شدن محتوا را ارسال کنید:",
            "delete": "📝 دلیل حذف محتوا را ارسال کنید:",
        }[action]
        await query.edit_message_text(prompt)
        return


async def comment_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    _, action, comment_id = query.data.split(":")
    comment = get_comment(comment_id)
    if not comment:
        await query.edit_message_text("❌ نظر پیدا نشد.")
        return

    if action == "approve":
        resolve_comment(comment_id, query.from_user.id, "approve")
        await query.edit_message_text(f"✅ نظر {comment_id} تایید شد.")
        return

    context.user_data["admin_comment_reject_id"] = comment_id
    await query.edit_message_text("📝 دلیل رد نظر را ارسال کنید:")


async def admin_edit_reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.effective_user.id):
        return

    text = (update.message.text or "").strip()
    logger.info(
        "Admin text handler user_id=%s text=%r admin_panel=%s admin_radar_menu=%s radar_create=%s",
        update.effective_user.id,
        text,
        bool(context.user_data.get("admin_panel")),
        bool(context.user_data.get("admin_radar_menu")),
        bool(context.user_data.get("radar_create")),
    )
    if context.user_data.get("radar_create"):
        if await handle_radar_creation_message(update, context):
            stop_admin_update("radar_create_message")

    if context.user_data.get("admin_radar_menu") and not (
        context.user_data.get("admin_comment_reject_id")
        or context.user_data.get("admin_reason_action")
    ):
        if text == ADMIN_RADAR_NEW:
            await start_radar_creation(update, context)
            stop_admin_update("admin_radar_new")
        if text == ADMIN_RADAR_DRAFTS:
            await send_admin_radar_list(update.message, "draft")
            stop_admin_update("admin_radar_drafts")
        if text == ADMIN_RADAR_READY:
            await send_admin_radar_list(update.message, "ready")
            stop_admin_update("admin_radar_ready")
        if text == ADMIN_RADAR_PUBLISHED:
            await send_admin_radar_list(update.message, "published")
            stop_admin_update("admin_radar_published")
        if text == ADMIN_RADAR_FAILED:
            await send_admin_radar_list(update.message, "failed")
            stop_admin_update("admin_radar_failed")
        if text == ADMIN_RADAR_SOURCES:
            await send_admin_radar_sources(update.message)
            stop_admin_update("admin_radar_sources")
        if text == ADMIN_RADAR_REVIEW:
            items = load_review_queue(limit=20)
            queue_text, visible_items = radar_review_queue_payload(items)
            await update.message.reply_text(
                queue_text,
                reply_markup=radar_review_queue_keyboard(visible_items),
                disable_web_page_preview=True,
            )
            stop_admin_update("admin_radar_review")
        if text == ADMIN_RADAR_BACK:
            context.user_data.pop("admin_radar_menu", None)
            await update.message.reply_text("به پنل ادمین برگشتید.", reply_markup=admin_panel_inline_keyboard())
            stop_admin_update("admin_radar_back")
        logger.warning("Unhandled admin Radar menu text=%r user_id=%s", text, update.effective_user.id)
        await update.message.reply_text(
            "این منو منقضی شده است. لطفاً دوباره /admin را باز کنید.",
            reply_markup=admin_radar_menu_keyboard(),
        )
        stop_admin_update("admin_radar_menu_unhandled")

    if context.user_data.get("admin_panel") and not (
        context.user_data.get("admin_comment_reject_id")
        or context.user_data.get("admin_reason_action")
    ):
        if text == ADMIN_PENDING:
            await show_pending_admin_items(update)
            stop_admin_update("admin_pending")
        if text == ADMIN_COMMENTS:
            await send_pending_comments(update.message)
            stop_admin_update("admin_comments")
        if text == ADMIN_REPORTS:
            await show_admin_reports(update)
            stop_admin_update("admin_reports")
        if text == ADMIN_RADAR_MANAGE:
            clear_non_admin_flow_state(context)
            context.user_data["admin_radar_menu"] = True
            logger.info("Entering admin Radar menu user_id=%s", update.effective_user.id)
            await send_admin_radar_menu(update.message)
            stop_admin_update("admin_radar_manage")
        if text == ADMIN_RADAR:
            await send_admin_radar_list(update.message)
            stop_admin_update("admin_radar_legacy")
        if text == ADMIN_RADAR_DRAFTS:
            await send_admin_radar_list(update.message, "draft")
            stop_admin_update("admin_panel_radar_drafts")
        if text == ADMIN_RADAR_NEW:
            await start_radar_creation(update, context)
            stop_admin_update("admin_panel_radar_new")
        if text == ADMIN_RADAR_READY:
            await send_admin_radar_list(update.message, "ready")
            stop_admin_update("admin_panel_radar_ready")
        if text == ADMIN_RADAR_PUBLISHED:
            await send_admin_radar_list(update.message, "published")
            stop_admin_update("admin_panel_radar_published")
        if text == ADMIN_RADAR_FAILED:
            await send_admin_radar_list(update.message, "failed")
            stop_admin_update("admin_panel_radar_failed")
        if text == ADMIN_RADAR_REVIEW:
            items = load_review_queue(limit=20)
            queue_text, visible_items = radar_review_queue_payload(items)
            await update.message.reply_text(
                queue_text,
                reply_markup=radar_review_queue_keyboard(visible_items),
                disable_web_page_preview=True,
            )
            stop_admin_update("admin_panel_radar_review")
        if text == ADMIN_HOME:
            context.user_data.pop("admin_panel", None)
            from handlers.start import MAIN_MENU

            await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
            stop_admin_update("admin_home")
        logger.warning("Unhandled admin panel text=%r user_id=%s", text, update.effective_user.id)
        await update.message.reply_text(
            "این منو منقضی شده است. لطفاً دوباره /admin را باز کنید.",
            reply_markup=admin_panel_inline_keyboard(),
        )
        stop_admin_update("admin_panel_unhandled")

    comment_id = context.user_data.pop("admin_comment_reject_id", None)
    if comment_id:
        reason = update.message.text.strip()
        resolve_comment(comment_id, update.effective_user.id, "reject", reason)
        await update.message.reply_text(f"❌ نظر {comment_id} رد شد.")
        stop_admin_update("admin_comment_reject")

    action = context.user_data.pop("admin_reason_action", None)
    content_id = context.user_data.pop("admin_reason_content_id", None)
    if not action or not content_id:
        return

    reason = update.message.text.strip()
    content = get_content(content_id)
    if not content:
        await update.message.reply_text("❌ محتوا پیدا نشد.")
        stop_admin_update("admin_reason_missing_content")

    resolve_review(content_id, update.effective_user.id, action, reason)
    label = "پیام" if is_hayat_content(content) else "آگهی"

    if action == "need_edit":
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=need_edit_text(content, reason),
            reply_markup=need_edit_keyboard(content),
        )
        await update.message.reply_text(f"✅ {content_id} به draft برگشت.")
        stop_admin_update("admin_need_edit")

    if action == "reject":
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=(
                f"❌ {label} شما رد شد.\n\n"
                f"🆔 {content['human_id']}\n\n"
                f"دلیل ادمین:\n{reason}"
            ),
        )
        await update.message.reply_text(f"✅ {content_id} رد شد.")
        stop_admin_update("admin_reject")

    await context.bot.send_message(
        chat_id=content["user_telegram_id"],
        text=(
            f"🗑 {label} شما حذف شد.\n\n"
            f"🆔 {content['human_id']}\n\n"
            f"دلیل ادمین:\n{reason}"
        ),
    )
    await update.message.reply_text(f"✅ {content_id} حذف شد.")
    stop_admin_update("admin_delete")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی ادمین ندارید.")
        return

    logger.info("Opening admin panel user_id=%s", update.effective_user.id)
    context.user_data.clear()
    context.user_data["admin_panel"] = True
    await update.message.reply_text("پنل ادمین باز شد.", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        "👨‍💼 پنل ادمین ویترین",
        reply_markup=admin_panel_inline_keyboard(),
    )


async def show_pending_admin_items(update: Update):
    pending = list_pending_content()
    if not pending:
        await update.message.reply_text("موردی در انتظار بررسی وجود ندارد.", reply_markup=admin_panel_inline_keyboard())
        return

    for content in pending:
        await update.message.reply_text(
            admin_content_text(content),
            reply_markup=admin_review_keyboard(content["human_id"]),
        )


async def show_admin_reports(update: Update):
    reports = list_active_reports()
    if reports:
        text = "🚨 گزارش‌های فعال\n\n" + "\n".join(
            f"{report['human_id']} برای {report['content_human_id']}: {report['reason']}"
            for report in reports
        )
        await update.message.reply_text(text, reply_markup=admin_panel_inline_keyboard())
    else:
        await update.message.reply_text("گزارش فعالی وجود ندارد.", reply_markup=admin_panel_inline_keyboard())
