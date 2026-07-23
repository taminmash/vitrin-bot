import logging
from datetime import datetime
from zoneinfo import ZoneInfo

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
from radar_engine.job_presentation import is_job
from radar_engine.job_expiration import job_temporal_state
from radar_engine.persian_detail import split_telegram_text
from radar_engine.renderer import (
    build_radar_deep_link,
    channel_button_specs,
    clean_text as render_clean_text,
    details_button_specs,
    expired_job_button_specs,
    field_log,
    format_date as render_format_date,
    job_details_button_specs,
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

REQUEST_ACTION_UNAVAILABLE_TEXT = (
    "🚧 این خدمت در حال راه‌اندازی است\n\n"
    "امکان ثبت درخواست اقدام از طریق ویترین در حال حاضر فعال نیست.\n\n"
    "این بخش در حال تکمیل و به‌روزرسانی است و به‌زودی در دسترس قرار خواهد گرفت.\n\n"
    "از شکیبایی شما سپاسگزاریم. 🙏"
)


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
            [
                InlineKeyboardButton("💼 آگهی‌های شغلی", callback_data="radar:type:job"),
                InlineKeyboardButton("🛍 تخفیف‌ها و آفرها", callback_data="radar:type:discount"),
            ],
            [
                InlineKeyboardButton("🎉 رویدادهای نزدیک", callback_data="radar:type:event"),
                InlineKeyboardButton("📡 اخبار مهم اسپانیا", callback_data="radar:type:all"),
            ],
            [InlineKeyboardButton("🚨 هشدارهای فوری", callback_data="radar:type:alert")],
            [InlineKeyboardButton("⬅️ بازگشت به پنل اصلی", callback_data="radar:home")],
        ]
    )


def deep_link_for_item(item):
    return build_radar_deep_link(BOT_USERNAME, item["id"])


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
    return telegram_keyboard(channel_button_specs(item, deep_link_for_item(item), counts))


def full_item_keyboard(item):
    return telegram_keyboard(overview_button_specs(item, deep_link_for_item(item)))


def details_keyboard(item):
    category = item.get("type") or item.get("category")
    if is_job(category, item.get("structured_data")) and job_temporal_state(item).expired:
        builder = expired_job_button_specs
    else:
        builder = job_details_button_specs if is_job(category, item.get("structured_data")) else details_button_specs
    return telegram_keyboard(builder(item, deep_link_for_item(item), channel_url_for_item(item)))


def expired_item_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 خانه", callback_data="radar:home")]])


def request_action_unavailable_keyboard(item_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ بازگشت به صفحه قبلی", callback_data=f"radar:details:{item_id}")],
            [InlineKeyboardButton("🏠 بازگشت به صفحه اصلی", callback_data="radar:home")],
        ]
    )


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


async def show_radar_overview(query):
    await query.message.reply_text(radar_overview_text(), reply_markup=radar_keyboard())


async def send_radar_item_message(message, item):
    logger.info("Rendering Radar bot overview fields=%s", renderer_field_log(item))
    chunks = split_telegram_text(format_radar_bot_overview(item))
    for index, chunk in enumerate(chunks):
        await message.reply_text(
            chunk,
            reply_markup=full_item_keyboard(item) if index == len(chunks) - 1 else None,
            disable_web_page_preview=True,
        )


async def send_radar_details_message(message, item):
    logger.info("Rendering Radar details fields=%s", renderer_field_log(item))
    chunks = split_telegram_text(format_radar_details(item))
    for index, chunk in enumerate(chunks):
        await message.reply_text(
            chunk,
            reply_markup=details_keyboard(item) if index == len(chunks) - 1 else None,
            disable_web_page_preview=True,
        )


async def send_missing_radar_item(message):
    await message.reply_text(
        "این آیتم رادار پیدا نشد یا مهلت آن تمام شده است.",
        reply_markup=expired_item_keyboard(),
    )


async def edit_or_reply(query, text, reply_markup):
    try:
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except TelegramError as error:
        logger.warning("Could not edit Radar callback message; sending fallback: %s", error)
        await query.message.reply_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )


def load_job_for_navigation(item_id):
    if not item_id:
        return None
    try:
        item = get_active_or_demo_radar_item(item_id)
    except Exception:
        item = None
    if not item:
        try:
            item = get_radar_item(item_id)
        except Exception:
            item = None
    if not item or not is_job(item.get("type") or item.get("category"), item.get("structured_data")):
        return None
    return item


async def open_radar_deep_link(update: Update, item_id: str):
    try:
        item = get_active_or_demo_radar_item(item_id)
    except Exception:
        item = None
    if not item:
        try:
            historical = get_radar_item(item_id)
        except Exception:
            historical = None
        if historical and is_job(
            historical.get("type") or historical.get("category"),
            historical.get("structured_data"),
        ):
            item = historical
    if not item:
        await send_missing_radar_item(update.message)
        return
    if is_job(item.get("type") or item.get("category"), item.get("structured_data")):
        await send_radar_details_message(update.message, item)
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

    data = query.data or ""
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

    if data == "radar:apply" or data.startswith("radar:apply:"):
        item_id = data.removeprefix("radar:apply:").strip() if ":" in data else ""
        item = load_job_for_navigation(item_id)
        if not item:
            await edit_or_reply(query, "این آگهی شغلی پیدا نشد.", expired_item_keyboard())
            return
        if job_temporal_state(item).expired:
            await edit_or_reply(query, format_radar_details(item), details_keyboard(item))
            return
        await edit_or_reply(
            query,
            REQUEST_ACTION_UNAVAILABLE_TEXT,
            request_action_unavailable_keyboard(item_id),
        )
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
        await send_radar_item_message(query.message, item)
        return

    if data.startswith("radar:details:"):
        item_id = data.removeprefix("radar:details:")
        item = load_job_for_navigation(item_id)
        if not item:
            try:
                item = get_active_or_demo_radar_item(item_id)
            except Exception:
                item = None
        if not item:
            await send_missing_radar_item(query.message)
            return
        if is_job(item.get("type") or item.get("category"), item.get("structured_data")):
            await edit_or_reply(query, format_radar_details(item), details_keyboard(item))
        else:
            await send_radar_details_message(query.message, item)
        return

    if data.startswith("radar:type:"):
        radar_type = data.removeprefix("radar:type:")
        item = first_radar_item(radar_type)
        if not item:
            await query.message.reply_text(
                "در حال حاضر محتوایی در این بخش موجود نیست.",
                reply_markup=radar_keyboard(),
            )
            return
        await send_radar_item_message(query.message, item)
