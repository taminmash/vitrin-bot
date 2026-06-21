#!/usr/bin/env python3
import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config_v2 import BOT_TOKEN
from database.db import init_db
from handlers.admin import admin_callback, admin_edit_reason_handler
from handlers.menu import menu_handler
from handlers.post_create import post_handler, user_post_callback
from handlers.profile import profile_handler
from handlers.start import start


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(user_post_callback, pattern=r"^userpost:"))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_reason_handler),
        group=-1,
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, profile_handler), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, post_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler), group=2)

    logging.info("Vitrin Spain Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
