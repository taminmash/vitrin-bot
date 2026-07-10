import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config_v2 import ADMIN_IDS, CHANNEL_HAYAT, CHANNEL_VITRIN, TECH_SUPPORT_IDS
from database.db import (
    create_radar_item,
    get_comment,
    get_content,
    get_radar_item,
    list_active_reports,
    list_admin_radar_items,
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
from handlers.radar import channel_post_keyboard, format_radar_channel_post


ADMIN_PENDING = "📥 موارد در انتظار بررسی"
ADMIN_REPORTS = "🚩 گزارش‌ها"
ADMIN_BACK = "🏠 بازگشت"
ADMIN_RADAR_MANAGE = "📡 مدیریت رادار"
ADMIN_RADAR = "📡 انتشار رادار"
ADMIN_RADAR_NEW = "➕ محتوای جدید"
ADMIN_RADAR_DRAFTS = "📝 پیش‌نویس‌ها"
ADMIN_RADAR_READY = "✅ آماده انتشار"
ADMIN_RADAR_PUBLISHED = "📤 منتشرشده‌ها"
ADMIN_RADAR_FAILED = "❌ ناموفق‌ها"
ADMIN_RADAR_SOURCES = "📚 منابع رادار"
RADAR_STATUS_LABELS = {
    "draft": "پیش‌نویس",
    "ready": "آماده انتشار",
    "published": "منتشرشده",
    "expired": "منقضی",
    "failed": "ناموفق",
}
ADMIN_PANEL_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(ADMIN_PENDING)],
        [KeyboardButton(ADMIN_REPORTS)],
        [KeyboardButton(ADMIN_RADAR_MANAGE)],
        [KeyboardButton(ADMIN_BACK)],
    ],
    resize_keyboard=True,
)

ADMIN_RADAR_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(ADMIN_RADAR_NEW)],
        [KeyboardButton(ADMIN_RADAR_DRAFTS)],
        [KeyboardButton(ADMIN_RADAR_READY)],
        [KeyboardButton(ADMIN_RADAR_PUBLISHED)],
        [KeyboardButton(ADMIN_RADAR_SOURCES)],
        [KeyboardButton(ADMIN_BACK)],
    ],
    resize_keyboard=True,
)

RADAR_CREATE_FIELDS = [
    ("title", "عنوان رادار را بفرستید:"),
    ("type", "نوع/دسته را بفرستید: alert, discount, event, job, legal, travel, family, weather, transport, economy, education"),
    ("city", "شهر را بفرستید یا بنویسید: کل اسپانیا"),
    ("summary", "خلاصه کوتاه را بفرستید:"),
    ("ai_reason", "چرا مهم است؟ یک توضیح کوتاه بفرستید:"),
    ("body", "جزئیات کامل را بفرستید:"),
    ("source_name", "نام منبع را بفرستید:"),
    ("source_url", "لینک منبع رسمی را بفرستید:"),
    ("start_date", "تاریخ شروع را با فرمت YYYY-MM-DD بفرستید یا بنویسید امروز:"),
    ("end_date", "تاریخ پایان را با فرمت YYYY-MM-DD بفرستید یا بنویسید 7 یعنی هفت روز بعد:"),
    ("urgency", "درجه فوریت را بفرستید: low, medium, high, urgent"),
    ("audience_tags", "تگ‌های مخاطب را با ویرگول جدا کنید:"),
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


def is_admin(user_id):
    return user_id in ADMIN_IDS or user_id in TECH_SUPPORT_IDS


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
    return (
        "پیش‌نمایش محتوای رادار\n\n"
        f"{format_radar_channel_post(item)}\n\n"
        "این متن نسخه کوتاه کانال است. جزئیات کامل داخل ربات نمایش داده می‌شود."
    )


def create_payload_from_radar_data(data, status):
    radar_type = normalize_radar_type(data.get("type"))
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    return {
        "title": data.get("title"),
        "type": radar_type,
        "category": TYPE_CATEGORY.get(radar_type, radar_type),
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
        "audience_tags": data.get("audience_tags") or [],
        "ai_tags": data.get("audience_tags") or [],
        "original_text": data.get("body"),
        "original_language": "fa",
        "is_verified": True,
        "is_published": status in ("ready", "published"),
    }


async def publish_radar_item(context, item):
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
    rows.append([InlineKeyboardButton("↩️ بازگشت", callback_data="admin_radar:back")])
    return InlineKeyboardMarkup(rows)


def radar_item_preview_keyboard(item):
    rows = []
    if radar_status(item) != "published":
        rows.append([InlineKeyboardButton("📤 انتشار در کانال", callback_data=f"admin_radar:publish:{item['id']}")])
    rows.append([InlineKeyboardButton("↩️ بازگشت به لیست", callback_data="admin_radar:list")])
    return InlineKeyboardMarkup(rows)


async def send_admin_radar_list(message, only_status=None):
    grouped = list_admin_radar_items()
    if only_status:
        grouped = {status: items if status == only_status else [] for status, items in grouped.items()}
    await message.reply_text(
        radar_admin_list_text(grouped),
        reply_markup=radar_admin_list_keyboard(grouped),
    )


async def send_admin_radar_menu(message):
    await message.reply_text(
        "📡 مدیریت رادار\n\n"
        "یکی از بخش‌های رادار را انتخاب کنید:",
        reply_markup=ADMIN_RADAR_KEYBOARD,
    )


async def send_admin_radar_sources(message):
    sources = list_source_registry()
    if not sources:
        await message.reply_text("منبع فعالی برای رادار ثبت نشده است.", reply_markup=ADMIN_RADAR_KEYBOARD)
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

    await message.reply_text("\n".join(lines).strip(), reply_markup=ADMIN_RADAR_KEYBOARD)


async def start_radar_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["radar_create"] = {"step": 0, "data": {}}
    await update.message.reply_text(RADAR_CREATE_FIELDS[0][1], reply_markup=ADMIN_RADAR_KEYBOARD)


async def handle_radar_creation_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("radar_create")
    if not state:
        return False

    text = update.message.text.strip()
    if text == ADMIN_BACK:
        context.user_data.pop("radar_create", None)
        await update.message.reply_text("ایجاد محتوای رادار لغو شد.", reply_markup=ADMIN_PANEL_KEYBOARD)
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

    try:
        if field == "type":
            radar_type = normalize_radar_type(text)
            data["type"] = radar_type
            data["category"] = TYPE_CATEGORY.get(radar_type, radar_type)
        elif field in ("start_date", "end_date"):
            data[field] = parse_radar_date(text)
        elif field == "urgency":
            data[field] = text if text in ("low", "medium", "high", "urgent") else "low"
        elif field == "audience_tags":
            data[field] = [tag.strip() for tag in text.replace("،", ",").split(",") if tag.strip()]
        else:
            data[field] = text
    except Exception:
        await update.message.reply_text("فرمت این مقدار درست نیست. لطفاً دوباره بفرستید.")
        return True

    step += 1
    state["step"] = step
    if step < len(RADAR_CREATE_FIELDS):
        await update.message.reply_text(RADAR_CREATE_FIELDS[step][1])
        return True

    await update.message.reply_text(radar_create_preview_text(data), reply_markup=radar_create_keyboard())
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
    if not is_admin(query.from_user.id):
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return

    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else "list"

    if action in ("list", "back"):
        await edit_admin_radar_list(query)
        return

    if action == "create":
        operation = parts[2] if len(parts) > 2 else ""
        data = context.user_data.get("radar_create", {}).get("data")
        if operation == "cancel":
            context.user_data.pop("radar_create", None)
            await query.edit_message_text("ایجاد محتوای رادار لغو شد.")
            return
        if operation == "edit":
            if not data:
                await query.edit_message_text("پیش‌نویسی برای ویرایش وجود ندارد.")
                return
            context.user_data["radar_create"] = {"step": 0, "data": data}
            await query.edit_message_text(RADAR_CREATE_FIELDS[0][1])
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
        preview = format_radar_channel_post(item)
        await query.edit_message_text(
            preview,
            reply_markup=radar_item_preview_keyboard(item),
            disable_web_page_preview=True,
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

    text = update.message.text
    if context.user_data.get("radar_create"):
        if await handle_radar_creation_message(update, context):
            return

    if context.user_data.get("admin_radar_menu") and not (
        context.user_data.get("admin_comment_reject_id")
        or context.user_data.get("admin_reason_action")
    ):
        if text == ADMIN_RADAR_NEW:
            await start_radar_creation(update, context)
            return
        if text == ADMIN_RADAR_DRAFTS:
            await send_admin_radar_list(update.message, "draft")
            return
        if text == ADMIN_RADAR_READY:
            await send_admin_radar_list(update.message, "ready")
            return
        if text == ADMIN_RADAR_PUBLISHED:
            await send_admin_radar_list(update.message, "published")
            return
        if text == ADMIN_RADAR_SOURCES:
            await send_admin_radar_sources(update.message)
            return
        if text == ADMIN_BACK:
            context.user_data.pop("admin_radar_menu", None)
            await update.message.reply_text("به پنل ادمین برگشتید.", reply_markup=ADMIN_PANEL_KEYBOARD)
            return

    if context.user_data.get("admin_panel") and not (
        context.user_data.get("admin_comment_reject_id")
        or context.user_data.get("admin_reason_action")
    ):
        if text == ADMIN_PENDING:
            await show_pending_admin_items(update)
            return
        if text == ADMIN_REPORTS:
            await show_admin_reports(update)
            return
        if text == ADMIN_RADAR_MANAGE:
            context.user_data["admin_radar_menu"] = True
            await send_admin_radar_menu(update.message)
            return
        if text == ADMIN_RADAR:
            await send_admin_radar_list(update.message)
            return
        if text == ADMIN_RADAR_DRAFTS:
            await send_admin_radar_list(update.message, "draft")
            return
        if text == ADMIN_RADAR_NEW:
            await start_radar_creation(update, context)
            return
        if text == ADMIN_RADAR_READY:
            await send_admin_radar_list(update.message, "ready")
            return
        if text == ADMIN_RADAR_PUBLISHED:
            await send_admin_radar_list(update.message, "published")
            return
        if text == ADMIN_RADAR_FAILED:
            await send_admin_radar_list(update.message, "failed")
            return
        if text == ADMIN_BACK:
            context.user_data.pop("admin_panel", None)
            from handlers.start import MAIN_MENU

            await update.message.reply_text("به منوی اصلی برگشتید.", reply_markup=MAIN_MENU)
            return

    comment_id = context.user_data.pop("admin_comment_reject_id", None)
    if comment_id:
        reason = update.message.text.strip()
        resolve_comment(comment_id, update.effective_user.id, "reject", reason)
        await update.message.reply_text(f"❌ نظر {comment_id} رد شد.")
        return

    action = context.user_data.pop("admin_reason_action", None)
    content_id = context.user_data.pop("admin_reason_content_id", None)
    if not action or not content_id:
        return

    reason = update.message.text.strip()
    content = get_content(content_id)
    if not content:
        await update.message.reply_text("❌ محتوا پیدا نشد.")
        return

    resolve_review(content_id, update.effective_user.id, action, reason)
    label = "پیام" if is_hayat_content(content) else "آگهی"

    if action == "need_edit":
        await context.bot.send_message(
            chat_id=content["user_telegram_id"],
            text=need_edit_text(content, reason),
            reply_markup=need_edit_keyboard(content),
        )
        await update.message.reply_text(f"✅ {content_id} به draft برگشت.")
        return

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
        return

    await context.bot.send_message(
        chat_id=content["user_telegram_id"],
        text=(
            f"🗑 {label} شما حذف شد.\n\n"
            f"🆔 {content['human_id']}\n\n"
            f"دلیل ادمین:\n{reason}"
        ),
    )
    await update.message.reply_text(f"✅ {content_id} حذف شد.")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی ادمین ندارید.")
        return

    context.user_data["admin_panel"] = True
    await update.message.reply_text(
        "👨‍💼 پنل ادمین ویترین",
        reply_markup=ADMIN_PANEL_KEYBOARD,
    )


async def show_pending_admin_items(update: Update):
    pending = list_pending_content()
    if not pending:
        await update.message.reply_text("موردی در انتظار بررسی وجود ندارد.", reply_markup=ADMIN_PANEL_KEYBOARD)
        return

    for content in pending:
        await update.message.reply_text(
            admin_content_text(content),
            reply_markup=admin_review_keyboard(content["human_id"]),
        )


async def show_admin_reports(update: Update):
    reports = list_active_reports()
    if reports:
        text = "🚩 گزارش‌های فعال\n\n" + "\n".join(
            f"{report['human_id']} برای {report['content_human_id']}: {report['reason']}"
            for report in reports
        )
        await update.message.reply_text(text, reply_markup=ADMIN_PANEL_KEYBOARD)
    else:
        await update.message.reply_text("گزارش فعالی وجود ندارد.", reply_markup=ADMIN_PANEL_KEYBOARD)
