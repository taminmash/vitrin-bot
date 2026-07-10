from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import BOT_USERNAME
from database.db import count_available_radar_by_type, get_active_radar_item, list_available_radar_items
from handlers.start import MAIN_MENU, send_home_dashboard


RADAR_TYPES = {
    "alert": {"label": "فوری", "emoji": "🔥", "demo": 1},
    "discount": {"label": "تخفیف‌ها", "emoji": "💶", "demo": 3},
    "event": {"label": "ایونت‌ها", "emoji": "🎉", "demo": 2},
    "job": {"label": "کار", "emoji": "💼", "demo": 4},
    "legal": {"label": "قوانین", "emoji": "🏛", "demo": 1},
    "travel": {"label": "سفر", "emoji": "✈️", "demo": 2},
    "family": {"label": "خانواده", "emoji": "👨‍👩‍👧", "demo": 1},
    "weather": {"label": "هوا", "emoji": "🌦", "demo": 1},
    "transport": {"label": "حمل‌ونقل", "emoji": "🚇", "demo": 1},
    "economy": {"label": "اقتصاد", "emoji": "💰", "demo": 1},
    "education": {"label": "آموزش", "emoji": "📚", "demo": 1},
}

DEMO_ITEMS = {
    "alert": {
        "title": "هشدار فوری نمونه",
        "summary": "این یک نمونه نمایشی است تا ساختار رادار قبل از ورود داده واقعی قابل تست باشد.",
        "body": "جزئیات کامل این آیتم پس از ثبت محتوای واقعی در دیتابیس نمایش داده می‌شود.",
        "type": "alert",
        "city": "همه شهرها",
        "province": "اسپانیا",
        "country": "Spain",
        "urgency": "urgent",
        "priority_score": 90,
        "audience_tags": ["همه فارسی‌زبانان اسپانیا"],
        "source_url": "https://t.me/vitrinspain",
        "source_name": "Vitrin Spain",
    },
    "discount": {
        "title": "تخفیف و آفر نمونه",
        "summary": "نمونه تخفیف برای نمایش ظاهر آیتم‌های رادار اسپانیا.",
        "body": "جزئیات کامل آفر در این بخش داخل ربات نمایش داده می‌شود.",
        "type": "discount",
        "city": "Madrid",
        "province": "Madrid",
        "country": "Spain",
        "urgency": "medium",
        "priority_score": 50,
        "audience_tags": ["دانشجوها", "خانواده‌ها"],
        "source_url": "https://t.me/vitrinspain",
        "source_name": "Vitrin Spain",
    },
    "event": {
        "title": "رویداد نزدیک شما",
        "summary": "نمونه رویداد برای تست دسته ایونت‌ها در رادار اسپانیا.",
        "body": "زمان، مکان و نکات کامل رویداد داخل ربات نمایش داده می‌شود.",
        "type": "event",
        "city": "Barcelona",
        "province": "Catalonia",
        "country": "Spain",
        "urgency": "medium",
        "priority_score": 45,
        "audience_tags": ["جامعه فارسی‌زبان"],
        "source_url": "https://t.me/vitrinspain",
        "source_name": "Vitrin Spain",
    },
}


def now_spain():
    return datetime.now(ZoneInfo("Europe/Madrid"))


def radar_counts():
    try:
        counts = count_available_radar_by_type()
    except Exception:
        counts = {}
    return {key: counts.get(key) or data["demo"] for key, data in RADAR_TYPES.items()}


def radar_overview_text():
    counts = radar_counts()
    updated_at = now_spain().strftime("%H:%M")
    return (
        "📡 رادار اسپانیا\n\n"
        "تا این لحظه برای شما:\n\n"
        f"🔥 {counts['alert']} هشدار فوری\n"
        f"💶 {counts['discount']} تخفیف جدید\n"
        f"🎉 {counts['event']} رویداد\n"
        f"💼 {counts['job']} فرصت شغلی\n"
        f"🏛 {counts['legal']} قانون و خدمات اداری\n"
        f"✈️ {counts['travel']} فرصت سفر\n"
        f"👨‍👩‍👧 {counts['family']} خبر خانواده\n\n"
        f"آخرین بروزرسانی: {updated_at}"
    )


def radar_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔥 فوری", callback_data="radar:type:alert")],
            [
                InlineKeyboardButton("💶 تخفیف‌ها", callback_data="radar:type:discount"),
                InlineKeyboardButton("🎉 ایونت‌ها", callback_data="radar:type:event"),
            ],
            [
                InlineKeyboardButton("💼 کار", callback_data="radar:type:job"),
                InlineKeyboardButton("🏛 قوانین", callback_data="radar:type:legal"),
            ],
            [
                InlineKeyboardButton("✈️ سفر", callback_data="radar:type:travel"),
                InlineKeyboardButton("👨‍👩‍👧 خانواده", callback_data="radar:type:family"),
            ],
            [
                InlineKeyboardButton("🌦 هوا", callback_data="radar:type:weather"),
                InlineKeyboardButton("🚇 حمل‌ونقل", callback_data="radar:type:transport"),
            ],
            [
                InlineKeyboardButton("💰 اقتصاد", callback_data="radar:type:economy"),
                InlineKeyboardButton("📚 آموزش", callback_data="radar:type:education"),
            ],
            [
                InlineKeyboardButton("📍 شهر من", callback_data="radar:type:city"),
                InlineKeyboardButton("⭐ همه", callback_data="radar:type:all"),
            ],
            [InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="radar:home")],
        ]
    )


def deep_link_for_item(item):
    return f"https://t.me/{BOT_USERNAME}?start=radar_{item['id']}"


def channel_post_keyboard(item):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🤖 مشاهده جزئیات در ویترین", url=deep_link_for_item(item))]]
    )


def full_item_keyboard(item):
    rows = []
    if item.get("source_url"):
        rows.append([InlineKeyboardButton("🔗 منبع رسمی", url=item["source_url"])])
    rows.append([InlineKeyboardButton("📤 اشتراک‌گذاری", switch_inline_query=deep_link_for_item(item))])
    rows.append([InlineKeyboardButton("🏠 خانه", callback_data="radar:home")])
    return InlineKeyboardMarkup(rows)


def expired_item_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 خانه", callback_data="radar:home")]])


def format_date(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def audience_text(item):
    tags = item.get("audience_tags") or item.get("ai_tags") or []
    if isinstance(tags, str):
        return tags
    return "، ".join(tags) if tags else "عموم کاربران"


def location_text(item):
    return " / ".join(
        value for value in [item.get("city"), item.get("province"), item.get("country")] if value
    ) or "اسپانیا"


def shorten_words(text, max_words=36):
    words = (text or "-").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip("،.") + "..."


def short_channel_lines(item, max_words=28):
    source_text = item.get("ai_reason") or item.get("summary") or "-"
    short = shorten_words(source_text, max_words)
    words = short.split()
    if len(words) <= 14:
        return [short]
    return [" ".join(words[:14]), " ".join(words[14:28])]


def category_emoji(item):
    radar_type = item.get("type") or "alert"
    return RADAR_TYPES.get(radar_type, {}).get("emoji", "📡")


def clean_channel_title(title):
    text = (title or "-").strip()
    for data in RADAR_TYPES.values():
        emoji = data.get("emoji")
        if emoji and text.startswith(emoji):
            return text[len(emoji):].strip()
    for emoji in ("🚨", "💶", "🎉", "💼", "🏛", "✈️", "👨‍👩‍👧", "🌦", "🚇", "💰", "📚", "🔥"):
        if text.startswith(emoji):
            return text[len(emoji):].strip()
    return text


def radar_item_text(item):
    radar_type = item.get("type") or "alert"
    emoji = category_emoji(item)
    reason = item.get("ai_reason") or item.get("summary") or "-"
    body = item.get("body") or item.get("original_text") or item.get("summary") or "-"
    return (
        "📡 رادار اسپانیا\n\n"
        f"{emoji} {item.get('title') or '-'}\n\n"
        f"📍 محدوده: {location_text(item)}\n"
        f"⏳ اعتبار/مهلت: {format_date(item.get('start_date'))} تا {format_date(item.get('end_date') or item.get('expires_at'))}\n"
        f"🎯 مناسب برای: {audience_text(item)}\n\n"
        "چرا مهم است؟\n"
        f"{reason}\n\n"
        "جزئیات:\n"
        f"{body}\n\n"
        "منبع رسمی:\n"
        f"{item.get('source_url') or item.get('source_name') or '-'}"
    )


def format_radar_channel_post(item):
    emoji = category_emoji(item)
    lines = [
        "📡 رادار اسپانیا",
        "",
        f"{emoji} {clean_channel_title(item.get('title'))}",
        "",
        "💡 چرا مهم است؟",
        *short_channel_lines(item),
        "",
        "🤖 جزئیات کامل داخل ربات",
        "",
        f"🔗 منبع: {item.get('source_name') or '-'}",
    ]
    return "\n".join(lines)


def demo_item(radar_type):
    item = DEMO_ITEMS.get(radar_type) or DEMO_ITEMS["alert"]
    return {**item, "id": f"demo-{radar_type}", "start_date": now_spain(), "end_date": None}


def first_radar_item(radar_type):
    query_type = None if radar_type in ("all", "city") else radar_type
    try:
        items = list_available_radar_items(query_type, limit=1)
    except Exception:
        items = []
    if items:
        return items[0]
    if radar_type in ("all", "city"):
        radar_type = "alert"
    return demo_item(radar_type)


async def show_radar_overview(query):
    await query.message.reply_text(radar_overview_text(), reply_markup=radar_keyboard())


async def send_radar_item_message(message, item):
    await message.reply_text(
        radar_item_text(item),
        reply_markup=full_item_keyboard(item),
        disable_web_page_preview=True,
    )


async def send_missing_radar_item(message):
    await message.reply_text(
        "این آیتم رادار پیدا نشد یا مهلت آن تمام شده است.",
        reply_markup=expired_item_keyboard(),
    )


async def open_radar_deep_link(update: Update, item_id: str):
    try:
        item = get_active_radar_item(item_id)
    except Exception:
        item = None
    if not item:
        await send_missing_radar_item(update.message)
        return
    await send_radar_item_message(update.message, item)


async def radar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "radar:open":
        await show_radar_overview(query)
        return

    if data == "radar:home":
        context.user_data.clear()
        await send_home_dashboard(update)
        return

    if data in ("radar:save", "radar:reminder"):
        await query.message.reply_text("این قابلیت در نسخه بعدی فعال می‌شود.", reply_markup=MAIN_MENU)
        return

    if data.startswith("radar:item:"):
        item_id = data.removeprefix("radar:item:")
        try:
            item = get_active_radar_item(item_id)
        except Exception:
            item = None
        if not item:
            await send_missing_radar_item(query.message)
            return
        await send_radar_item_message(query.message, item)
        return

    if data.startswith("radar:type:"):
        radar_type = data.removeprefix("radar:type:")
        await send_radar_item_message(query.message, first_radar_item(radar_type))
