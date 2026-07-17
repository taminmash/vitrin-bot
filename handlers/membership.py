from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config_v2 import CHANNEL_HAYAT, CHANNEL_HAYAT_LINK, CHANNEL_VITRIN, CHANNEL_VITRIN_LINK


logger = logging.getLogger(__name__)
ALLOWED_MEMBER_STATUSES = {"member", "administrator", "creator"}


def membership_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📡 عضویت در رادار اسپانیا", url=CHANNEL_VITRIN_LINK)],
            [InlineKeyboardButton("🏡 عضویت در حیات خلوت", url=CHANNEL_HAYAT_LINK)],
            [InlineKeyboardButton("✅ بررسی عضویت", callback_data="membership:check")],
        ]
    )


def membership_text():
    return (
        "🔒 برای استفاده از ویترین اسپانیا ابتدا باید عضو کانال‌های رسمی شوید.\n\n"
        "عضویت در کانال‌ها:\n\n"
        "📡 رادار اسپانیا\n\n"
        "🏡 حیات خلوت\n\n"
        "پس از عضویت روی دکمه زیر بزنید."
    )


def _is_member(chat_member) -> bool:
    if getattr(chat_member, "status", None) in ALLOWED_MEMBER_STATUSES:
        return True
    return bool(getattr(chat_member, "is_member", False))


async def has_required_memberships(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        memberships = [
            await context.bot.get_chat_member(CHANNEL_VITRIN, user_id),
            await context.bot.get_chat_member(CHANNEL_HAYAT, user_id),
        ]
    except Exception:
        logger.exception("Could not verify mandatory channel membership user_id=%s", user_id)
        return False
    return all(_is_member(member) for member in memberships)


async def show_membership_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query and update.effective_chat and update.effective_chat.type == "private":
        try:
            await query.edit_message_text(
                membership_text(),
                reply_markup=membership_keyboard(),
                disable_web_page_preview=True,
            )
            return
        except BadRequest:
            pass
    if query:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=membership_text(),
            reply_markup=membership_keyboard(),
            disable_web_page_preview=True,
        )
        return
    target = update.effective_message
    if target:
        await target.reply_text(
            membership_text(),
            reply_markup=membership_keyboard(),
            disable_web_page_preview=True,
        )


async def membership_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    verified = await has_required_memberships(context, user.id)
    is_check = bool(update.callback_query and update.callback_query.data == "membership:check")

    if not verified:
        if update.callback_query:
            await update.callback_query.answer("عضویت در هر دو کانال هنوز تأیید نشده است.", show_alert=True)
        await show_membership_gate(update, context)
        raise ApplicationHandlerStop

    if is_check:
        await update.callback_query.answer("عضویت شما تأیید شد ✅")
        from database.db import get_or_create_user, user_exists
        from handlers.start import send_home_dashboard

        first_start = not user_exists(user.id)
        get_or_create_user(user)
        context.user_data.clear()
        await send_home_dashboard(update, show_banner=first_start)
        raise ApplicationHandlerStop
