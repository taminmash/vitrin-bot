#!/usr/bin/env python3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from config import (BOT_TOKEN, ADMIN_ID, CATEGORIES, COMING_SOON_SUBCATS,
                    ANONYMOUS_SUBCATS, EXPERIENCE_SUBCATS,
                    CATEGORY_CHANNELS, DEFAULT_CHANNEL)
from texts import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SELECT_CATEGORY, SELECT_SUBCATEGORY, SELECT_EXPERIENCE, WRITE_MESSAGE, CONFIRM_MESSAGE = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    cats = list(CATEGORIES.keys())
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(cats[i], callback_data=f"cat:{cats[i]}")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(cats[i+1], callback_data=f"cat:{cats[i+1]}"))
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)

    # ارسال عکس + متن خوش‌آمدگویی
    if update.message:
        if WELCOME_IMAGE_URL:
            await update.message.reply_photo(
                photo=WELCOME_IMAGE_URL,
                caption=WELCOME_CAPTION
            )
        else:
            with open("welcome.png", "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=WELCOME_CAPTION
                )
        await update.message.reply_text(WELCOME, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(WELCOME, reply_markup=reply_markup)
    return SELECT_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("cat:", "")
    context.user_data['category'] = category
    subcats = CATEGORIES.get(category, [])

    keyboard = []
    for sub in subcats:
        keyboard.append([InlineKeyboardButton(sub, callback_data=f"sub:{sub}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back:main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    cat_texts = {
        "💼 کار و درآمد": CAT_WORK,
        "🏠 خانه‌یابی": CAT_HOUSING,
        "🛒 خرید و فروش": CAT_SHOP,
        "🔧 خدمات و ارتباطات": CAT_SERVICES,
        "💰 سرمایه و وام": CAT_INVESTMENT,
        "🌿 حیاط خلوت اسپانیا": CAT_COMMUNITY,
        "📢 تبلیغات ویژه": CAT_ADS,
        "💬 پشتیبانی": CAT_SUPPORT,
    }

    text = cat_texts.get(category, f"بخش {category}\n\n👇 زیربخش موردنظر را انتخاب کنید:")
    await query.edit_message_text(text, reply_markup=reply_markup)
    return SELECT_SUBCATEGORY

async def select_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back:main":
        keyboard = []
        cats = list(CATEGORIES.keys())
        for i in range(0, len(cats), 2):
            row = [InlineKeyboardButton(cats[i], callback_data=f"cat:{cats[i]}")]
            if i + 1 < len(cats):
                row.append(InlineKeyboardButton(cats[i+1], callback_data=f"cat:{cats[i+1]}"))
            keyboard.append(row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(WELCOME, reply_markup=reply_markup)
        return SELECT_CATEGORY

    subcategory = query.data.replace("sub:", "")
    context.user_data['subcategory'] = subcategory
    category = context.user_data.get('category', '')

    # بخش‌های به زودی
    if subcategory in COMING_SOON_SUBCATS or "(به زودی)" in subcategory:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(COMING_SOON, reply_markup=reply_markup)
        return SELECT_SUBCATEGORY

    # ارتباط با ادمین
    if subcategory == "💛 ارتباط با ادمین":
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(SUBCATEGORY_TEXTS.get(subcategory, ""), reply_markup=reply_markup)
        return SELECT_SUBCATEGORY

    # تجربه‌ها - نمایش زیرمجموعه‌های موضوعی
    if subcategory == "🧭 تجربه‌ها":
        keyboard = []
        for exp in EXPERIENCE_SUBCATS:
            keyboard.append([InlineKeyboardButton(exp, callback_data=f"exp:{exp}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(SUB_EXPERIENCES, reply_markup=reply_markup)
        return SELECT_EXPERIENCE

    text = SUBCATEGORY_TEXTS.get(subcategory, "📝 پیام خود را بنویسید:")
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return WRITE_MESSAGE

async def select_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("cat:"):
        return await select_category(update, context)

    experience = query.data.replace("exp:", "")
    context.user_data['experience'] = experience
    category = context.user_data.get('category', '')

    text = f"""🧭 تجربه‌ها — {experience}

جهت ثبت رایگان تجربه خود در این موضوع، پیام خود را بنویسید.

⚠️ ارسال عکس، لینک و فیلم مجاز نیست.
✅ شماره تماس و آیدی تلگرام مجاز است.

📝 پیام خود را بنویسید:"""

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"sub:🧭 تجربه‌ها")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return WRITE_MESSAGE

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    context.user_data['message'] = user_message
    category = context.user_data.get('category', '')
    subcategory = context.user_data.get('subcategory', '')
    experience = context.user_data.get('experience', '')

    display_sub = f"{subcategory} — {experience}" if experience else subcategory

    text = FORM_CONFIRM.format(
        message=user_message,
        category=category,
        subcategory=display_sub
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ تأیید و ارسال", callback_data="confirm:yes"),
            InlineKeyboardButton("✏️ ویرایش", callback_data="confirm:edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)
    return CONFIRM_MESSAGE

async def confirm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm:edit":
        subcategory = context.user_data.get('subcategory', '')
        text = SUBCATEGORY_TEXTS.get(subcategory, "📝 پیام خود را بنویسید:")
        await query.edit_message_text(text)
        return WRITE_MESSAGE

    if query.data == "confirm:yes":
        user = query.from_user
        category = context.user_data.get('category', '')
        subcategory = context.user_data.get('subcategory', '')
        experience = context.user_data.get('experience', '')
        message = context.user_data.get('message', '')

        display_sub = f"{subcategory} — {experience}" if experience else subcategory
        is_anonymous = subcategory in ANONYMOUS_SUBCATS

        if is_anonymous:
            user_name = "ناشناس"
        else:
            user_name = f"@{user.username}" if user.username else user.full_name

        admin_text = ADMIN_NEW_POST.format(
            user_name=user_name,
            user_id=user.id,
            category=category,
            subcategory=display_sub,
            message=message
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=f"admin:approve:{user.id}"),
                InlineKeyboardButton("✏️ ویرایش", callback_data=f"admin:edit:{user.id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"admin:reject:{user.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # تعیین کانال مناسب
        target_channel = CATEGORY_CHANNELS.get(category, DEFAULT_CHANNEL)

        context.bot_data[f"post_{user.id}"] = {
            'category': category,
            'subcategory': display_sub,
            'message': message,
            'user_name': user_name,
            'is_anonymous': is_anonymous,
            'target_channel': target_channel,
        }

        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=reply_markup)
        await query.edit_message_text(FORM_SUBMITTED)
        return ConversationHandler.END

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ شما ادمین نیستید!", show_alert=True)
        return

    parts = query.data.split(":")
    action = parts[1]
    user_id = int(parts[2])
    post = context.bot_data.get(f"post_{user_id}", {})

    if action == "approve":
        is_anonymous = post.get('is_anonymous', False)
        target_channel = post.get('target_channel', DEFAULT_CHANNEL)

        if is_anonymous:
            channel_text = f"""📌 {post.get('category')} | {post.get('subcategory')}

{post.get('message')}

━━━━━━━━━━━━━━━
🤖 @VitrinSpainBot"""
        else:
            channel_text = f"""📌 {post.get('category')} | {post.get('subcategory')}

{post.get('message')}

━━━━━━━━━━━━━━━
👤 {post.get('user_name')}
🤖 @VitrinSpainBot"""

        await context.bot.send_message(chat_id=target_channel, text=channel_text)
        await context.bot.send_message(chat_id=user_id, text=FORM_APPROVED)
        await query.edit_message_text(f"✅ تأیید شد.\n\n{query.message.text}")

    elif action == "edit":
        context.bot_data[f"waiting_reason_{ADMIN_ID}"] = {'action': 'edit', 'user_id': user_id}
        await query.edit_message_text(query.message.text + "\n\n⏳ دلیل ویرایش را بنویسید...")
        await context.bot.send_message(chat_id=ADMIN_ID, text=ADMIN_ASK_REASON.format(action="ویرایش"))

    elif action == "reject":
        context.bot_data[f"waiting_reason_{ADMIN_ID}"] = {'action': 'reject', 'user_id': user_id}
        await query.edit_message_text(query.message.text + "\n\n⏳ دلیل رد را بنویسید...")
        await context.bot.send_message(chat_id=ADMIN_ID, text=ADMIN_ASK_REASON.format(action="رد"))

async def admin_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    waiting = context.bot_data.get(f"waiting_reason_{ADMIN_ID}")
    if not waiting:
        return

    reason = update.message.text
    action = waiting['action']
    user_id = waiting['user_id']

    if action == "edit":
        await context.bot.send_message(chat_id=user_id, text=FORM_NEEDS_EDIT.format(reason=reason))
        await update.message.reply_text("✅ پیام ویرایش به کاربر ارسال شد.")
    elif action == "reject":
        await context.bot.send_message(chat_id=user_id, text=FORM_REJECTED.format(reason=reason))
        await update.message.reply_text("✅ پیام رد به کاربر ارسال شد.")

    del context.bot_data[f"waiting_reason_{ADMIN_ID}"]

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(select_category, pattern="^cat:"),
        ],
        states={
            SELECT_CATEGORY: [CallbackQueryHandler(select_category, pattern="^cat:")],
            SELECT_SUBCATEGORY: [
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
                CallbackQueryHandler(select_subcategory, pattern="^back:"),
                CallbackQueryHandler(select_category, pattern="^cat:"),
            ],
            SELECT_EXPERIENCE: [
                CallbackQueryHandler(select_experience, pattern="^exp:"),
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
                CallbackQueryHandler(select_category, pattern="^cat:"),
            ],
            WRITE_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                CallbackQueryHandler(select_category, pattern="^cat:"),
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
            ],
            CONFIRM_MESSAGE: [CallbackQueryHandler(confirm_message, pattern="^confirm:")],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^admin:"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID),
        admin_reason
    ))

    print("🤖 بات ویترین اسپانیا شروع به کار کرد...")
    app.run_polling()

if __name__ == "__main__":
    main()
