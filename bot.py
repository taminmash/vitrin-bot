#!/usr/bin/env python3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from config import (BOT_TOKEN, ADMIN_ID, CATEGORIES, SUBCAT_LABELS,
                    COMING_SOON_SUBCATS, ANONYMOUS_SUBCATS, HAYAT_SUBCATS,
                    HAYAT_MAIN_SUBCATS, CATEGORY_CHANNELS, DEFAULT_CHANNEL,
                    SUPPORT_SUBCATS)
from texts import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SELECT_CATEGORY, SELECT_SUBCATEGORY, SELECT_HAYAT_TOPIC, WRITE_MESSAGE, CONFIRM_MESSAGE = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    cats = list(CATEGORIES.keys())
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(cats[i], callback_data=f"cat:{cats[i]}")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(cats[i+1], callback_data=f"cat:{cats[i+1]}"))
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(WELCOME, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(WELCOME, reply_markup=reply_markup)
    return SELECT_CATEGORY

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("cat:", "")
    context.user_data['category'] = category
    context.user_data['experience'] = ''
    subcats = CATEGORIES.get(category, [])

    keyboard = []
    for label, code in subcats:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"sub:{code}")])
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
        "💬 پشتیبانی 💛💜": CAT_SUPPORT,
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

    subcode = query.data.replace("sub:", "")
    sublabel = SUBCAT_LABELS.get(subcode, subcode)
    context.user_data['subcategory'] = subcode
    context.user_data['subcategory_label'] = sublabel
    category = context.user_data.get('category', '')

    # بخش‌های به زودی
    if subcode in COMING_SOON_SUBCATS:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(COMING_SOON, reply_markup=reply_markup)
        return SELECT_SUBCATEGORY

    # پشتیبانی - مستقیم به ادمین
    if subcode in SUPPORT_SUBCATS:
        text = """💬 پشتیبان فنی 💛💜

پیام خود را بنویسید.
تیم ویترین در اسرع وقت پاسخ خواهد داد. 💛

📝 پیام خود را بنویسید:"""
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return WRITE_MESSAGE

    # زیربخش‌های حیاط خلوت
    if subcode in HAYAT_MAIN_SUBCATS:
        context.user_data['hayat_type'] = subcode
        context.user_data['hayat_type_label'] = sublabel
        keyboard = []
        for topic in HAYAT_SUBCATS:
            keyboard.append([InlineKeyboardButton(topic, callback_data=f"htopic:{topic}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        type_texts = {
            "sub_hayat_anon": SUB_ANONYMOUS,
            "sub_hayat_exp": SUB_EXPERIENCES,
            "sub_hayat_event": SUB_DORHAM,
        }
        text = type_texts.get(subcode, "موضوع را انتخاب کنید:")
        await query.edit_message_text(text, reply_markup=reply_markup)
        return SELECT_HAYAT_TOPIC

    # بقیه زیربخش‌ها
    text = SUBCATEGORY_TEXTS.get(subcode, "📝 پیام خود را بنویسید:")
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return WRITE_MESSAGE

async def select_hayat_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("cat:"):
        category = query.data.replace("cat:", "")
        context.user_data['category'] = category
        return await select_category(update, context)

    topic = query.data.replace("htopic:", "")
    context.user_data['experience'] = topic
    hayat_type = context.user_data.get('hayat_type', 'sub_hayat_exp')
    hayat_label = context.user_data.get('hayat_type_label', '🧭 تجربه‌ها')
    category = context.user_data.get('category', '')

    is_dorham = hayat_type == "sub_hayat_event"

    if is_dorham:
        text = f"""🎉 دورهمی — {topic}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند. 💜

📝 پیام خود را بنویسید:"""
    else:
        text = f"""{hayat_label} — {topic}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند. 💜

📝 پیام خود را بنویسید:"""

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"sub:{hayat_type}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return WRITE_MESSAGE

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    context.user_data['message'] = user_message
    category = context.user_data.get('category', '')
    subcategory_label = context.user_data.get('subcategory_label', '')
    experience = context.user_data.get('experience', '')

    display_sub = f"{subcategory_label} — {experience}" if experience else subcategory_label

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
        subcode = context.user_data.get('subcategory', '')
        experience = context.user_data.get('experience', '')
        hayat_label = context.user_data.get('hayat_type_label', '')

        if experience and subcode in HAYAT_MAIN_SUBCATS:
            is_dorham = subcode == "sub_hayat_event"
            if is_dorham:
                text = f"""🎉 دورهمی — {experience}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند. 💜

📝 پیام خود را بنویسید:"""
            else:
                text = f"""{hayat_label} — {experience}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.

📝 پیام خود را بنویسید:"""
        elif subcode in SUPPORT_SUBCATS:
            text = """💬 پشتیبان فنی 💛💜

📝 پیام خود را بنویسید:"""
        else:
            text = SUBCATEGORY_TEXTS.get(subcode, "📝 پیام خود را بنویسید:")

        await query.edit_message_text(text)
        return WRITE_MESSAGE

    if query.data == "confirm:yes":
        user = query.from_user
        category = context.user_data.get('category', '')
        subcode = context.user_data.get('subcategory', '')
        subcategory_label = context.user_data.get('subcategory_label', '')
        experience = context.user_data.get('experience', '')
        message = context.user_data.get('message', '')

        display_sub = f"{subcategory_label} — {experience}" if experience else subcategory_label
        is_anonymous = subcode in ANONYMOUS_SUBCATS
        is_support = subcode in SUPPORT_SUBCATS

        if is_anonymous:
            user_name = "ناشناس"
        else:
            user_name = f"@{user.username}" if user.username else user.full_name

        # پشتیبانی مستقیم به ادمین
        if is_support:
            support_text = f"""📩 پیام پشتیبانی جدید

👤 کاربر: {f"@{user.username}" if user.username else user.full_name}
🆔 آی‌دی: {user.id}

📝 پیام:
━━━━━━━━━━━━━━━
{message}
━━━━━━━━━━━━━━━"""
            await context.bot.send_message(chat_id=ADMIN_ID, text=support_text)
            await query.edit_message_text("""✅ پیام شما به تیم پشتیبانی ارسال شد.

در اسرع وقت پاسخ خواهیم داد. 💛""")
            return ConversationHandler.END

        admin_text = ADMIN_NEW_POST.format(
            user_name=user_name,
            user_id=user.id if not is_anonymous else "ناشناس",
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
            SELECT_CATEGORY: [
                CallbackQueryHandler(select_category, pattern="^cat:"),
            ],
            SELECT_SUBCATEGORY: [
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
                CallbackQueryHandler(select_subcategory, pattern="^back:"),
                CallbackQueryHandler(select_category, pattern="^cat:"),
            ],
            SELECT_HAYAT_TOPIC: [
                CallbackQueryHandler(select_hayat_topic, pattern="^htopic:"),
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
                CallbackQueryHandler(select_category, pattern="^cat:"),
            ],
            WRITE_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                CallbackQueryHandler(select_category, pattern="^cat:"),
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
            ],
            CONFIRM_MESSAGE: [
                CallbackQueryHandler(confirm_message, pattern="^confirm:"),
            ],
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
