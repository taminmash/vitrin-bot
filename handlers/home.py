from types import SimpleNamespace

from telegram import Update
from telegram.ext import ContextTypes

from handlers.post_create import start_hayat_post, start_post
from handlers.profile import profile_start
from handlers.start import MAIN_MENU, send_home_dashboard


HELP_TEXT = (
    "ℹ️ راهنمای ویترین اسپانیا\n\n"
    "🟡 ثبت آگهی در ویترین:\n"
    "برای ثبت آگهی، روی دکمه «ثبت آگهی در ویترین» بزنید و مراحل را کامل کنید.\n\n"
    "🟣 پیام ناشناس حیاط خلوت:\n"
    "برای ارسال پیام ناشناس، روی دکمه «پیام ناشناس حیاط خلوت» بزنید.\n\n"
    "👤 پروفایل من:\n"
    "برای دیدن آگهی‌ها، پیش‌نویس‌ها و وضعیت ارسال‌ها.\n\n"
    "📡 رادار اسپانیا:\n"
    "برای دیدن هشدارها، تخفیف‌ها، رویدادها، کار، قوانین و خبرهای کاربردی روز.\n\n"
    "🆘 پشتیبانی:\n"
    "@VitrinSpainAdmin"
)


def callback_update(update: Update):
    return SimpleNamespace(
        message=update.callback_query.message,
        effective_user=update.effective_user,
        effective_chat=update.effective_chat,
    )


async def home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.removeprefix("home:")
    synthetic_update = callback_update(update)

    if action == "create_vitrin":
        await start_post(synthetic_update, context, post_type="vitrin")
        return

    if action == "create_hayat":
        await start_hayat_post(synthetic_update, context)
        return

    if action == "profile":
        await profile_start(synthetic_update, context)
        return

    if action == "help":
        await query.message.reply_text(HELP_TEXT, reply_markup=MAIN_MENU, disable_web_page_preview=True)
        return

    if action == "dashboard":
        context.user_data.clear()
        await send_home_dashboard(update)
