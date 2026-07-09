from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config_v2 import BOT_USERNAME
from database.db import count_available_radar_by_type, list_available_radar_items
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


def item_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("❤️ ذخیره", callback_data="radar:save"),
                InlineKeyboardButton("🔔 یادآوری", callback_data="radar:reminder"),
            ],
            [InlineKeyboardButton("📤 اشتراک‌گذاری", switch_inline_query="رادار اسپانیا")],
            [InlineKeyboardButton("🏠 بازگشت", callback_data="radar:open")],
        ]
    )


def format_date(value):
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def audience_text(item):
    tags = item.get("audience_tags") or []
    if isinstance(tags, str):
        return tags
    return "، ".join(tags) if tags else "عموم کاربران"


def radar_item_text(item):
    radar_type = item.get("type") or "alert"
    emoji = RADAR_TYPES.get(radar_type, {}).get("emoji", "📡")
    location = " / ".join(
        value for value in [item.get("city"), item.get("province"), item.get("country")] if value
    ) or "اسپانیا"
    summary = item.get("summary") or "-"
    reason = summary if len(summary) <= 120 else summary[:117] + "..."
    return (
        "📡 رادار اسپانیا\n\n"
        f"{emoji} {item.get('title') or '-'}\n\n"
        f"📍 محدوده: {location}\n"
        f"⏳ زمان: {format_date(item.get('start_date'))} تا {format_date(item.get('end_date'))}\n"
        f"🎯 مناسب برای: {audience_text(item)}\n\n"
        "چرا مهم است؟\n"
        f"{reason}\n\n"
        "خلاصه:\n"
        f"{summary}\n\n"
        "🔗 منبع:\n"
        f"{item.get('source_url') or item.get('source_name') or '-'}"
    )


def format_radar_channel_post(item):
    radar_type = item.get("type") or "alert"
    emoji = RADAR_TYPES.get(radar_type, {}).get("emoji", "📡")
    location = " / ".join(
        value for value in [item.get("city"), item.get("province"), item.get("country")] if value
    ) or "اسپانیا"
    reason = item.get("ai_reason") or item.get("summary") or "-"
    summary = item.get("ai_summary") or item.get("summary") or "-"
    source = item.get("source_url") or item.get("source_name") or "-"
    parts = [
        "📡 رادار اسپانیا",
        "",
        f"{emoji} {item.get('title') or '-'}",
        "",
        f"📍 محدوده: {location}",
        f"⏳ زمان: {format_date(item.get('start_date'))} تا {format_date(item.get('end_date'))}",
        "",
        "چرا مهم است؟",
        reason,
        "",
        "خلاصه:",
        summary,
        "",
        "🔗 منبع:",
        source,
    ]
    if BOT_USERNAME:
        parts.extend(["", "🤖 ورود به ربات ویترین:", f"https://t.me/{BOT_USERNAME}"])
    return "\n".join(parts)


def demo_item(radar_type):
    item = DEMO_ITEMS.get(radar_type) or DEMO_ITEMS["alert"]
    return {**item, "start_date": now_spain(), "end_date": None}


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

    if data.startswith("radar:type:"):
        radar_type = data.removeprefix("radar:type:")
        await query.message.reply_text(radar_item_text(first_radar_item(radar_type)), reply_markup=item_keyboard())
