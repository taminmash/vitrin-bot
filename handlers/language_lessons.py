"""Interactive callbacks, reactions, and feedback for language lessons."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config_v2 import ADMIN_IDS, BOT_USERNAME, TECH_SUPPORT_IDS
from database.db import (
    delete_language_lesson_comment, get_language_lesson_comment,
    get_language_lesson_discussion_post, get_language_lesson_reaction_counts,
    mark_language_lesson_comment_failed, mark_language_lesson_comment_published,
    save_language_lesson_comment, save_language_lesson_discussion_post,
    save_language_lesson_reaction, save_language_lesson_report,
)

logger = logging.getLogger(__name__)
LEVEL_PATTERN = re.compile(r"^[a-z0-9_-]{1,16}$")
MAX_FEEDBACK_LENGTH = 1000
FEEDBACK_STATE_KEY = "language_lesson_feedback"
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
PLACEHOLDER_TEXTS = {
    "archive": "📚 آرشیو درس‌ها\n\nاین بخش در حال آماده‌سازی است.\n\nبه‌زودی امکان مرور تمام درس‌ها و واحدها فراهم خواهد شد.",
    "quiz": "🧠 آزمون\n\nاین بخش در حال آماده‌سازی است.\n\nبه‌زودی برای هر درس آزمون اختصاصی اضافه خواهد شد.",
    "practice": "🤖 تمرین در ربات\n\nاین بخش در حال آماده‌سازی است.\n\nبه‌زودی امکان تمرین مکالمه و تمرین‌های تعاملی فراهم خواهد شد.",
}

@dataclass(frozen=True)
class LessonCallback:
    action: str
    level: str
    lesson_number: int
    reaction: str | None = None


def parse_lesson_callback(data: str | None) -> LessonCallback | None:
    if not isinstance(data, str): return None
    parts = data.split(":")
    if len(parts) == 4 and parts[0] == "lesson" and parts[1] in {"archive", "quiz", "practice", "comment", "report"}:
        action, level, number = parts[1:]; reaction = None
    elif len(parts) == 5 and parts[:2] == ["lesson", "react"] and parts[2] in {"like", "dislike"}:
        action, reaction, level, number = "react", parts[2], parts[3], parts[4]
    else: return None
    if not LEVEL_PATTERN.fullmatch(level) or not (number.isascii() and number.isdecimal()): return None
    lesson_number = int(number)
    return LessonCallback(action, level, lesson_number, reaction) if lesson_number > 0 else None


def format_persian_number(value: int) -> str:
    return str(int(value)).translate(PERSIAN_DIGITS)


def build_language_lesson_keyboard(level: str, lesson_number: int, like_count: int, dislike_count: int) -> InlineKeyboardMarkup:
    suffix = f":{level}:{lesson_number}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 آرشیو", callback_data=f"lesson:archive{suffix}"), InlineKeyboardButton("🧠 آزمون", callback_data=f"lesson:quiz{suffix}")],
        [InlineKeyboardButton("🤖 تمرین", callback_data=f"lesson:practice{suffix}")],
        [InlineKeyboardButton(f"👍 پسندیدم · {format_persian_number(like_count)}", callback_data=f"lesson:react:like{suffix}"), InlineKeyboardButton(f"👎 نپسندیدم · {format_persian_number(dislike_count)}", callback_data=f"lesson:react:dislike{suffix}")],
        [InlineKeyboardButton("💬 نظر", callback_data=f"lesson:comment{suffix}"), InlineKeyboardButton("🚨 گزارش", callback_data=f"lesson:report{suffix}")],
    ])


def feedback_prompt(action: str, lesson_number: int) -> str:
    if action == "comment":
        return f"💬 ثبت نظر برای درس {lesson_number}\n\nنظر خود را اینجا بنویسید و ارسال کنید.\n\nپس از ارسال، نظر شما زیر پست درس نمایش داده می‌شود.\n\nبرای لغو /cancel را ارسال کنید."
    return f"🚨 گزارش مشکل درس {lesson_number}\n\nلطفاً گزارش خود را بنویسید و ارسال کنید.\n\nگزارش شما به واحد پشتیبانی و مدیریت ارسال خواهد شد.\n\nبرای لغو /cancel را ارسال کنید."


def begin_lesson_feedback(context, action, level, lesson_number):
    context.user_data[FEEDBACK_STATE_KEY] = {"action": action, "level": level, "lesson_number": lesson_number}


def is_private_callback(update): return bool(update.effective_chat and update.effective_chat.type == "private")

def lesson_deep_link(action, level, lesson_number):
    username = (BOT_USERNAME or "").lstrip("@")
    return f"https://t.me/{username}?start=lesson-{action}-{level}-{lesson_number}" if username else None


async def language_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query: return
    parsed = parse_lesson_callback(query.data)
    if not parsed:
        logger.warning("Ignoring malformed language lesson callback: %r", query.data); await query.answer("درخواست نامعتبر است.", show_alert=True); return
    if parsed.action in PLACEHOLDER_TEXTS:
        if is_private_callback(update): await query.answer(); await query.message.reply_text(PLACEHOLDER_TEXTS[parsed.action])
        else: await query.answer(PLACEHOLDER_TEXTS[parsed.action], show_alert=True)
        return
    if parsed.action == "react":
        try:
            save_language_lesson_reaction(query.from_user.id, parsed.level, parsed.lesson_number, parsed.reaction)
            counts = get_language_lesson_reaction_counts(parsed.level, parsed.lesson_number)
        except Exception:
            logger.exception("Unable to save language lesson reaction"); await query.answer("ثبت نظر انجام نشد. لطفاً دوباره تلاش کنید.", show_alert=True); return
        await query.answer("نظر مثبت شما ثبت شد ✅" if parsed.reaction == "like" else "نظر شما ثبت شد. ممنون که کمک می‌کنید آموزش بهتر شود.")
        try:
            await query.edit_message_reply_markup(build_language_lesson_keyboard(parsed.level, parsed.lesson_number, counts["like"], counts["dislike"]))
        except TelegramError:
            logger.info("Could not refresh language lesson reaction keyboard", exc_info=True)
        return
    if not is_private_callback(update):
        link = lesson_deep_link(parsed.action, parsed.level, parsed.lesson_number)
        if link: await query.answer(url=link)
        else: await query.answer("برای ادامه، ربات را باز کنید.", show_alert=True)
        return
    begin_lesson_feedback(context, parsed.action, parsed.level, parsed.lesson_number)
    await query.answer(); await query.message.reply_text(feedback_prompt(parsed.action, parsed.lesson_number))


def public_comment_text(comment, lesson_number):
    name = (comment.get("display_name") or "کاربر ویترین").strip()
    return f"💬 نظر درباره درس {lesson_number}\n\n👤 {name}\n\n{comment['comment_text']}"


def lesson_comment_delete_keyboard(comment_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🗑 حذف نظر", callback_data=f"admin:lesson-comment:delete:{comment_id}")]])


async def publish_lesson_comment(context, comment):
    mapping = get_language_lesson_discussion_post(comment["level"], comment["lesson_number"])
    if not mapping: return False
    kwargs = {"chat_id": mapping["discussion_chat_id"], "reply_to_message_id": mapping["discussion_message_id"], "reply_markup": lesson_comment_delete_keyboard(comment["id"])}
    try:
        photos = await context.bot.get_user_profile_photos(comment["user_telegram_id"], limit=1)
        if photos.total_count:
            sent = await context.bot.send_photo(photo=photos.photos[0][-1].file_id, caption=public_comment_text(comment, comment["lesson_number"]), **kwargs)
        else:
            sent = await context.bot.send_message(text=public_comment_text(comment, comment["lesson_number"]), **kwargs)
        mark_language_lesson_comment_published(comment["id"], sent.chat_id, sent.message_id)
        return True
    except TelegramError:
        logger.exception("Unable to publish language lesson comment")
        mark_language_lesson_comment_failed(comment["id"])
        return False


async def notify_lesson_report(context, report, user):
    recipients = set(ADMIN_IDS) | set(TECH_SUPPORT_IDS)
    username = f"@{user.username}" if getattr(user, "username", None) else "ندارد"
    timestamp = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M")
    text = f"🚨 گزارش جدید درس زبان\n\nسطح: {report['level']}\nدرس: {report['lesson_number']}\n\nمتن گزارش:\n{report['report_text']}\n\nکاربر:\nنام: {user.full_name}\nUsername: {username}\nTelegram ID: {user.id}\n\nتاریخ: {timestamp}"
    for recipient in recipients:
        try: await context.bot.send_message(chat_id=recipient, text=text)
        except TelegramError: logger.exception("Unable to deliver language lesson report to %s", recipient)


async def language_lesson_feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not (state := context.user_data.get(FEEDBACK_STATE_KEY)): return
    text = (update.message.text or "").strip()
    if not text: await update.message.reply_text("لطفاً متن بازخورد را ارسال کنید."); raise ApplicationHandlerStop
    if len(text) > MAX_FEEDBACK_LENGTH: await update.message.reply_text("متن بازخورد باید حداکثر ۱۰۰۰ کاراکتر باشد."); raise ApplicationHandlerStop
    try:
        if state["action"] == "comment":
            comment = save_language_lesson_comment(update.effective_user.id, state["level"], state["lesson_number"], text, update.effective_user.full_name)
            published = await publish_lesson_comment(context, comment)
            confirmation = "✅ نظر شما ثبت شد و زیر پست درس نمایش داده شد." if published else "✅ نظر شما ثبت شد و پس از آماده شدن بخش گفت‌وگو نمایش داده می‌شود."
        else:
            report = save_language_lesson_report(update.effective_user.id, state["level"], state["lesson_number"], text)
            await notify_lesson_report(context, report, update.effective_user)
            confirmation = "✅ گزارش شما ثبت و به واحد پشتیبانی و مدیریت ارسال شد."
    except Exception:
        logger.exception("Unable to save language lesson feedback"); await update.message.reply_text("ثبت بازخورد انجام نشد. لطفاً دوباره تلاش کنید."); raise ApplicationHandlerStop
    context.user_data.pop(FEEDBACK_STATE_KEY, None); await update.message.reply_text(confirmation); raise ApplicationHandlerStop


async def cancel_language_lesson_feedback(update, context):
    if FEEDBACK_STATE_KEY in context.user_data:
        context.user_data.pop(FEEDBACK_STATE_KEY, None); await update.message.reply_text("ثبت بازخورد لغو شد.")


def lesson_from_markup(message):
    markup = getattr(message, "reply_markup", None)
    for row in getattr(markup, "inline_keyboard", []) or []:
        for button in row:
            parsed = parse_lesson_callback(button.callback_data)
            if parsed: return parsed
    return None


async def language_lesson_discussion_mapping_handler(update, context):
    message = update.message
    origin = getattr(message, "forward_origin", None)
    if not message or not origin or not getattr(origin, "chat", None): return
    lesson = lesson_from_markup(message)
    if not lesson: return
    source_message_id = getattr(origin, "message_id", None)
    if source_message_id is None: return
    try: save_language_lesson_discussion_post(lesson.level, lesson.lesson_number, origin.chat.id, source_message_id, message.chat_id, message.message_id)
    except Exception: logger.exception("Unable to save language lesson discussion mapping")


async def language_lesson_admin_callback(update, context):
    query = update.callback_query
    if not query or query.from_user.id not in ADMIN_IDS:
        if query: await query.answer("دسترسی ندارید.", show_alert=True)
        return
    parts = (query.data or "").split(":")
    if len(parts) != 4 or parts[:3] != ["admin", "lesson-comment", "delete"] or not parts[3].isdigit():
        await query.answer("درخواست نامعتبر است.", show_alert=True); return
    comment = get_language_lesson_comment(int(parts[3]))
    if not comment or comment["status"] != "published": await query.answer("نظر پیدا نشد.", show_alert=True); return
    try:
        await context.bot.delete_message(comment["public_message_chat_id"], comment["public_message_id"])
    except TelegramError:
        logger.info("Lesson comment was already unavailable", exc_info=True)
    delete_language_lesson_comment(comment["id"])
    await query.answer("نظر حذف شد.")
