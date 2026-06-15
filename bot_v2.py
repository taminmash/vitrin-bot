from telegram.ext import (
    Application,
    CommandHandler,
)

from config_v2 import BOT_TOKEN
from database.db import init_db
from handlers.start import start


def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("Vitrin Spain V2 Started")

    app.run_polling()


if __name__ == "__main__":
    main()
