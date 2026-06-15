from telegram import Update
from telegram.ext import ContextTypes


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text

    if text == "🟡 ثبت آگهی در ویترین":
        await update.message.reply_text(
            "دسته آگهی را انتخاب کنید:\n\n"
            "💼 کار و درآمد\n"
            "🏠 خانه و اجاره\n"
            "🛒 خرید و فروش\n"
            "🔧 خدمات\n"
            "💰 سرمایه گذاری\n"
            "💶 خرید و فروش یورو\n"
            "📢 آگهی ویژه"
        )

    elif text == "🟣 ثبت پیام در حیاط خلوت":
        await update.message.reply_text(
            "نوع پیام را انتخاب کنید:\n\n"
            "💬 پیام ناشناس\n"
            "🧭 تجربه‌ها\n"
            "🎉 دورهمی\n"
            "📰 اخبار"
        )

    elif text == "👤 پروفایل من":
        await update.message.reply_text(
            "بخش پروفایل در حال ساخت است."
        )

    elif text == "ℹ️ راهنما":
        await update.message.reply_text(
            "راهنمای ویترین اسپانیا به زودی تکمیل می‌شود."
        )
