"""Callback routing and private feedback collection for language lessons."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config_v2 import BOT_USERNAME
from database.db import (
    save_language_lesson_comment,
    save_language_lesson_reaction,
    save_language_lesson_report,
)

logger = logging.getLogger(__name__)
LEVEL_PATTERN = re.compile(r"^[a-z0-9_-]{1,16}$")
MAX_FEEDBACK_LENGTH = 1000
FEEDBACK_STATE_KEY = "language_lesson_feedback"

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
    """Parse only supported, validated lesson callback payloads."""
    if not isinstance(data, str):
        return None
    parts = data.split(":")
    if len(parts) == 4 and parts[0] == "lesson" and parts[1] in {"archive", "quiz", "practice", "comment", "report"}:
        action, level, number = parts[1:]
        reaction = None
    elif len(parts) == 5 and parts[:2] == ["lesson", "react"] and parts[2] in {"like", "dislike"}:
        action, reaction, level, number = "react", parts[2], parts[3], parts[4]
    else:
        return None
    if not LEVEL_PATTERN.fullmatch(level) or not (number.isascii() and number.isdecimal()):
        return None
    lesson_number = int(number)
    if lesson_number < 1:
        return None
    return LessonCallback(action=action, level=level, lesson_number=lesson_number, reaction=reaction)


def feedback_prompt(action: str, lesson_number: int) -> str:
    if action == "comment":
        return f"💬 ثبت نظر برای درس {lesson_number}\n\nلطفاً نظر خود را در یک پیام ارسال کنید.\n\nبرای لغو /cancel را ارسال کنید."
    return f"🚨 گزارش مشکل درس {lesson_number}\n\nلطفاً مشکل درس را کوتاه توضیح دهید.\n\nبرای لغو /cancel را ارسال کنید."


def begin_lesson_feedback(context: ContextTypes.DEFAULT_TYPE, action: str, level: str, lesson_number: int) -> None:
    context.user_data[FEEDBACK_STATE_KEY] = {
        "action": action,
        "level": level,
        "lesson_number": lesson_number,
    }


def is_private_callback(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type == "private")


def comment_deep_link(level: str, lesson_number: int) -> str | None:
    username = (BOT_USERNAME or "").lstrip("@")
    if not username:
        return None
    return f"https://t.me/{username}?start=lesson-comment-{level}-{lesson_number}"


async def language_lesson_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    parsed = parse_lesson_callback(query.data)
    if not parsed:
        logger.warning("Ignoring malformed language lesson callback: %r", query.data)
        await query.answer("درخواست نامعتبر است.", show_alert=True)
        return

    if parsed.action in PLACEHOLDER_TEXTS:
        if is_private_callback(update):
            await query.answer()
            await query.message.reply_text(PLACEHOLDER_TEXTS[parsed.action])
        else:
            await query.answer(PLACEHOLDER_TEXTS[parsed.action], show_alert=True)
        return

    if parsed.action == "react":
        try:
            save_language_lesson_reaction(
                query.from_user.id, parsed.level, parsed.lesson_number, parsed.reaction
            )
        except Exception:
            logger.exception("Unable to save language lesson reaction")
            await query.answer("ثبت نظر انجام نشد. لطفاً دوباره تلاش کنید.", show_alert=True)
            return
        confirmation = (
            "نظر مثبت شما ثبت شد ✅"
            if parsed.reaction == "like"
            else "نظر شما ثبت شد. ممنون که کمک می‌کنید آموزش بهتر شود."
        )
        await query.answer(confirmation)
        return

    if not is_private_callback(update):
        link = comment_deep_link(parsed.level, parsed.lesson_number)
        message = "برای ارسال نظر، ابتدا @VitrinSpainBot را باز کنید."
        if link:
            message += f"\n{link}"
        await query.answer(message, show_alert=True)
        return

    begin_lesson_feedback(context, parsed.action, parsed.level, parsed.lesson_number)
    await query.answer()
    await query.message.reply_text(feedback_prompt(parsed.action, parsed.lesson_number))


async def language_lesson_feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Consume text only while a language-lesson feedback flow is active."""
    if not update.message:
        return
    state = context.user_data.get(FEEDBACK_STATE_KEY)
    if not state:
        return

    text = (update.message.text or "").strip()
    if text == "/cancel":
        context.user_data.pop(FEEDBACK_STATE_KEY, None)
        await update.message.reply_text("ثبت بازخورد لغو شد.")
        raise ApplicationHandlerStop
    if not text:
        await update.message.reply_text("لطفاً متن بازخورد را ارسال کنید.")
        raise ApplicationHandlerStop
    if len(text) > MAX_FEEDBACK_LENGTH:
        await update.message.reply_text("متن بازخورد باید حداکثر ۱۰۰۰ کاراکتر باشد.")
        raise ApplicationHandlerStop

    try:
        if state["action"] == "comment":
            save_language_lesson_comment(update.effective_user.id, state["level"], state["lesson_number"], text)
            confirmation = "✅ نظر شما ثبت شد. ممنون از همراهی شما."
        else:
            save_language_lesson_report(update.effective_user.id, state["level"], state["lesson_number"], text)
            # Reports are persisted for admin review. Add a safe admin notification here if one is introduced.
            confirmation = "✅ گزارش شما ثبت شد. ممنون از کمک شما."
    except Exception:
        logger.exception("Unable to save language lesson feedback")
        await update.message.reply_text("ثبت بازخورد انجام نشد. لطفاً دوباره تلاش کنید.")
        raise ApplicationHandlerStop

    context.user_data.pop(FEEDBACK_STATE_KEY, None)
    await update.message.reply_text(confirmation)
    raise ApplicationHandlerStop


async def cancel_language_lesson_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if FEEDBACK_STATE_KEY not in context.user_data:
        return
    context.user_data.pop(FEEDBACK_STATE_KEY, None)
    await update.message.reply_text("ثبت بازخورد لغو شد.")
