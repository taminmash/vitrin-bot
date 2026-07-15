#!/usr/bin/env python3
import logging
import traceback

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config_v2 import BOT_TOKEN
from database.db import init_db
from handlers.admin import (
    admin_callback,
    admin_edit_reason_handler,
    admin_panel,
    admin_radar_callback,
    comment_admin_callback,
    radar_review_command,
    radar_status_command,
    whoami,
)
from handlers.home import home_callback
from handlers.menu import menu_handler
from handlers.post_create import draft_callback, post_handler, published_callback, user_post_callback
from handlers.profile import profile_handler
from handlers.radar import radar_callback, radar_feedback_callback
from handlers.start import start
from radar_engine.scheduler import start_radar_scheduler, stop_radar_scheduler


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

FRIENDLY_ERROR = (
    "مشکلی پیش آمد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.\n"
    "@VitrinSpainAdmin"
)


async def error_handler(update, context):
    logging.error("Unhandled Telegram bot error: %s", context.error)
    logging.error("".join(traceback.format_exception(None, context.error, context.error.__traceback__)))
    if update and update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=FRIENDLY_ERROR)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    init_db()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(start_radar_scheduler)
        .post_shutdown(stop_radar_scheduler)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("radar_status", radar_status_command))
    app.add_handler(CommandHandler("radar_review", radar_review_command))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CallbackQueryHandler(admin_radar_callback, pattern=r"^admin_radar:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(comment_admin_callback, pattern=r"^comment:"))
    app.add_handler(CallbackQueryHandler(home_callback, pattern=r"^home:"))
    app.add_handler(CallbackQueryHandler(radar_feedback_callback, pattern=r"^radar_feedback:"))
    app.add_handler(CallbackQueryHandler(radar_callback, pattern=r"^radar:"))
    app.add_handler(CallbackQueryHandler(draft_callback, pattern=r"^draft:"))
    app.add_handler(CallbackQueryHandler(published_callback, pattern=r"^pub:"))
    app.add_handler(CallbackQueryHandler(user_post_callback, pattern=r"^userpost:"))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_reason_handler),
        group=-1,
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handler), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, post_handler), group=1)
    app.add_handler(MessageHandler((filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, post_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler), group=2)
    app.add_error_handler(error_handler)

    logging.info("Vitrin Spain Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
