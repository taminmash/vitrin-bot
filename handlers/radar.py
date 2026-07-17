import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config_v2 import BOT_USERNAME, CHANNEL_VITRIN, CHANNEL_VITRIN_LINK
from database.db import (
    count_available_radar_by_type,
    count_radar_reactions,
    get_active_radar_item,
    get_radar_item,
    list_available_radar_items,
    save_radar_reaction,
)
from handlers.start import MAIN_MENU, send_home_dashboard
from radar_engine.renderer import (
    channel_button_specs,
    clean_text as render_clean_text,
    details_button_specs,
    field_log,
    format_date as render_format_date,
    location_text as render_location_text,
    overview_button_specs,
    render_admin_preview,
    render_channel_post,
    render_details_page,
    render_ready_preview,
    summary_text as render_summary_text,
    reason_text as render_reason_text,
    shorten_words as render_shorten_words,
    type_emoji,
)


logger = logging.getLogger(__name__)


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
    return {key: int(counts.get(key) or 0) for key in RADAR_TYPES}


def radar_overview_text():
    counts = radar_counts()
    updated_at = now_spain().strftime("%H:%M")
    return (
        "📡 رادار اسپانیا\n\n"
        "تا این لحظه برای شما:\n\n"
        f"🚨 {counts['alert']} هشدار فوری\n"
        f"🛍 {counts['discount']} تخفیف\n"
        f"🎉 {counts['event']} رویداد\n"
        f"💼 {counts['job']} فرصت شغلی\n"
        f"📡 {sum(counts.values())} خبر مهم\n\n"
        f"آخرین بروزرسانی: {updated_at}"
    )


def radar_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💼 آگهی‌های شغلی", callback_data="radar:type:job"),
                InlineKeyboardButton("🛍 تخفیف‌ها و آفرها", callback_data="radar:type:discount"),
            ],
            [
                InlineKeyboardButton("🎉 رویدادهای نزدیک", callback_data="radar:type:event"),
                InlineKeyboardButton("📡 اخبار مهم اسپانیا", callback_data="radar:type:legal"),
            ],
            [InlineKeyboardButton("🚨 هشدارهای فوری", callback_data="radar:type:alert")],
            [InlineKeyboardButton("⬅️ بازگشت به پنل اصلی", callback_data="radar:home")],
        ]
    )


def deep_link_for_item(item):
    return f"https://t.me/{BOT_USERNAME}?start=radar_{item['id']}"


def get_radar_cta_label(item_type):
    return "📄 مشاهده جزئیات رویداد"


def telegram_keyboard(button_rows):
    rows = []
    for row in button_rows:
        buttons = []
        for button in row:
            kwargs = {}
            if button.callback_data:
                kwargs["callback_data"] = button.callback_data
            if button.url:
                kwargs["url"] = button.url
            if button.switch_inline_query:
                kwargs["switch_inline_query"] = button.switch_inline_query
            buttons.append(InlineKeyboardButton(button.text, **kwargs))
        rows.append(buttons)
    return InlineKeyboardMarkup(rows)


def channel_url_for_item(item):
    if item.get("channel_post_url"):
        return item["channel_post_url"]
    return CHANNEL_VITRIN_LINK or None


def channel_post_keyboard(item, reaction_counts=None):
    counts = reaction_counts
    if counts is None:
        try:
            counts = count_radar_reactions(item["id"])
        except Exception:
            counts = {"like": 0, "dislike": 0}
    return telegram_keyboard(
        channel_button_specs(item, deep_link_for_item(item), counts, share_url_for_item(item))
    )


def share_url_for_item(item):
    deep_link = deep_link_for_item(item)
    content = format_radar_details(item).strip()
    if len(content) > 700:
        content = content[:699].rstrip() + "…"
    return "https://t.me/share/url?" + urlencode({"url": deep_link, "text": content})


def full_item_keyboard(item, category=None):
    return telegram_keyboard(
        overview_button_specs(item, deep_link_for_item(item), share_url_for_item(item), category)
    )


def details_keyboard(item, category=None):
    return telegram_keyboard(
        details_button_specs(
            item,
            deep_link_for_item(item),
            channel_url_for_item(item),
            share_url_for_item(item),
            category,
        )
    )


def expired_item_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 خانه", callback_data="radar:home")]])


def format_date(value):
    return render_format_date(value)


def audience_text(item):
    from radar_engine.renderer import audience_text as renderer_audience_text

    return renderer_audience_text(item)


def location_text(item):
    return render_location_text(item)


def shorten_words(text, max_words=36):
    return render_shorten_words(text, max_words)


def category_emoji(item):
    return type_emoji(item)


def clean_text(value):
    return render_clean_text(value)


def radar_summary_text(item):
    return render_summary_text(item)


def radar_reason_text(item):
    return render_reason_text(item)


def format_radar_public_body(item):
    return render_channel_post(item)


def format_radar_channel_post(item):
    return render_channel_post(item)


def format_radar_bot_overview(item):
    return render_ready_preview(item)


def format_radar_details(item):
    return render_details_page(item)


def format_radar_admin_preview(item):
    return render_admin_preview(item)


def radar_item_text(item):
    return format_radar_bot_overview(item)


def renderer_field_log(item):
    return field_log(item)


def demo_item(radar_type):
    item = DEMO_ITEMS.get(radar_type) or DEMO_ITEMS["alert"]
    return {**item, "id": f"demo-{radar_type}", "start_date": now_spain(), "end_date": None}


def get_active_or_demo_radar_item(item_id):
    if str(item_id).startswith("demo-"):
        return demo_item(str(item_id).removeprefix("demo-"))
    return get_active_radar_item(item_id)


def first_radar_item(radar_type):
    query_type = None if radar_type in ("all", "city") else radar_type
    try:
        items = list_available_radar_items(query_type, limit=1)
    except Exception:
        items = []
    if items:
        return items[0]
    return None


RADAR_CATEGORY_LABELS = {
    "job": "💼 آگهی‌های شغلی",
    "discount": "🛍 تخفیف‌ها و آفرها",
    "event": "🎉 رویدادهای نزدیک",
    "legal": "📡 اخبار مهم اسپانیا",
    "alert": "🚨 هشدارهای فوری",
}


def radar_category_items(radar_type, limit=5):
    try:
        return list_available_radar_items(radar_type, limit=limit)
    except Exception:
        logger.exception("Failed to load Radar category type=%s", radar_type)
        return []


def radar_category_keyboard(radar_type, items):
    rows = [
        [InlineKeyboardButton((item.get("title") or "مشاهده محتوا")[:55], callback_data=f"radar:item:{item['id']}")]
        for item in items
    ]
    rows.append([InlineKeyboardButton("⬅️ بازگشت به رادار", callback_data="radar:open")])
    rows.append([InlineKeyboardButton("🏠 صفحه اصلی", callback_data="radar:home")])
    return InlineKeyboardMarkup(rows)


async def show_radar_category(query, radar_type):
    items = radar_category_items(radar_type)
    if not items:
        text = f"{RADAR_CATEGORY_LABELS.get(radar_type, '📡 رادار')}\n\nمحتوایی موجود نیست."
    else:
        text = (
            f"{RADAR_CATEGORY_LABELS.get(radar_type, '📡 رادار')}\n\n"
            "برای مشاهده، یکی از موارد زیر را انتخاب کنید:"
        )
    await query.message.reply_text(text, reply_markup=radar_category_keyboard(radar_type, items))


async def show_radar_overview(query):
    await query.message.reply_text(radar_overview_text(), reply_markup=radar_keyboard())


async def send_radar_item_message(message, item, category=None):
    logger.info("Rendering Radar bot overview fields=%s", renderer_field_log(item))
    await message.reply_text(
        format_radar_bot_overview(item),
        reply_markup=full_item_keyboard(item, category),
        disable_web_page_preview=True,
    )


async def send_radar_details_message(message, item, category=None):
    logger.info("Rendering Radar details fields=%s", renderer_field_log(item))
    await message.reply_text(
        format_radar_details(item),
        reply_markup=details_keyboard(item, category),
        disable_web_page_preview=True,
    )


async def send_missing_radar_item(message):
    await message.reply_text(
        "این آیتم رادار پیدا نشد یا مهلت آن تمام شده است.",
        reply_markup=expired_item_keyboard(),
    )


async def open_radar_deep_link(update: Update, item_id: str):
    try:
        item = get_active_or_demo_radar_item(item_id)
    except Exception:
        item = None
    if not item:
        await send_missing_radar_item(update.message)
        return
    await send_radar_item_message(update.message, item)


async def refresh_channel_feedback_keyboard(context, query, item):
    counts = count_radar_reactions(item["id"])
    keyboard = channel_post_keyboard(item, counts)

    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return
    except TelegramError as error:
        logger.warning("Could not edit Radar feedback keyboard from callback: %s", error)

    message_id = item.get("channel_message_id")
    if not message_id:
        return

    try:
        await context.bot.edit_message_reply_markup(
            chat_id=CHANNEL_VITRIN,
            message_id=message_id,
            reply_markup=keyboard,
        )
    except Exception as error:
        logger.warning("Could not edit Radar feedback keyboard for item %s: %s", item.get("id"), error)


async def radar_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[1] not in ("like", "dislike"):
        await query.answer("درخواست بازخورد معتبر نیست.", show_alert=True)
        return

    reaction = parts[1]
    item_id = parts[2]
    try:
        item = get_radar_item(item_id)
    except Exception:
        logger.exception("Failed to load Radar item for feedback")
        await query.answer("ثبت بازخورد فعلاً ممکن نیست. لطفاً بعداً دوباره تلاش کنید.", show_alert=True)
        return

    if not item:
        await query.answer("این آیتم رادار پیدا نشد.", show_alert=True)
        return

    try:
        save_radar_reaction(item_id, query.from_user.id, reaction)
    except Exception:
        logger.exception("Failed to save Radar reaction")
        await query.answer("ثبت بازخورد فعلاً ممکن نیست. لطفاً بعداً دوباره تلاش کنید.", show_alert=True)
        return

    if reaction == "like":
        await query.answer("نظر مثبت شما ثبت شد ✅")
    else:
        await query.answer("نظر شما ثبت شد. ممنون که کمک می‌کنید ویترین بهتر شود.")

    try:
        await refresh_channel_feedback_keyboard(context, query, item)
    except Exception:
        logger.exception("Failed to refresh Radar reaction counters")


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
            item = get_active_or_demo_radar_item(item_id)
        except Exception:
            item = None
        if not item:
            await send_missing_radar_item(query.message)
            return
        await send_radar_item_message(query.message, item, context.user_data.get("radar_category"))
        return

    if data.startswith("radar:details:"):
        item_id = data.removeprefix("radar:details:")
        try:
            item = get_active_or_demo_radar_item(item_id)
        except Exception:
            item = None
        if not item:
            await send_missing_radar_item(query.message)
            return
        await send_radar_details_message(query.message, item, context.user_data.get("radar_category"))
        return

    if data.startswith("radar:type:"):
        radar_type = data.removeprefix("radar:type:")
        context.user_data["radar_category"] = radar_type
        await show_radar_category(query, radar_type)
