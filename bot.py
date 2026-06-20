#!/usr/bin/env python3
import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config_v2 import BOT_TOKEN
from database.db import init_db
from handlers.admin import admin_callback
from handlers.post_create import (
    cancel,
    handle_text,
    start,
    user_post_callback,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(user_post_callback, pattern=r"^userpost:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
