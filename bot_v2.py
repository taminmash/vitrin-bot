from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config_v2 import BOT_TOKEN
from database.db import init_db

from handlers.start import start
from handlers.menu import menu_handler
from handlers.profile import profile_handler
from handlers.post_create import post_handler


def main():

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_handler,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            profile_handler,
        ),
        group=1,
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            post_handler,
        ),
        group=2,
    )

    print("Vitrin Spain V2 Started")

    app.run_polling()


if __name__ == "__main__":
    main()
