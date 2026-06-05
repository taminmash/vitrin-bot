#!/usr/bin/env python3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from config import (BOT_TOKEN, ADMIN_ID, CATEGORIES, SUBCAT_LABELS,
                    COMING_SOON_SUBCATS, ANONYMOUS_SUBCATS, HAYAT_SUBCATS,
                    HAYAT_MAIN_SUBCATS, VITRIN_SUBCATS, VITRIN_MAIN_SUBCATS,
                    CATEGORY_CHANNELS, DEFAULT_CHANNEL, SUPPORT_SUBCATS,
                    CHANNEL_VITRIN_LINK, CHANNEL_HAYAT_LINK)
from texts import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SELECT_CATEGORY, SELECT_SUBCATEGORY, SELECT_VITRIN_SUB, SELECT_HAYAT_TOPIC, WRITE_MESSAGE, CONFIRM_MESSAGE = range(6)

# توضیحات زیر هر دکمه منوی اصلی
CATEGORY_DESCRIPTIONS = {
    "ثبت پیام در حیاط خلوت": "ارسال ناشناس پیام، تجربه، اخبار و دورهمی",
    "ورود به کانال حیاط خلوت": "مشاهده گفتگوها — ناشناس",
    "ثبت پیام در ویترین": "ثبت رایگان آگهی کار، خونه، خرید، فروش و خدمات",
    "ورود به کانال ویترین": "مشاهده همه آگهی‌ها",
}

def build_main_keyboard():
    keyboard = []
    for cat in CATEGORIES.keys():
        desc = CATEGORY_DESCRIPTIONS.get(cat, "")
        if desc:
            # اگه توضیح داره — بدون ایموجی
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat:{cat}")])
            keyboard.append([InlineKeyboardButton(f"   {desc}", callback_data=f"cat:{cat}")])
        else:
            keyboard.append([InlineKeyboardButton(f"✨ {cat} ✨", callback_data=f"cat:{cat}")])
    return InlineKeyboardMarkup(keyboard)

def build_main_keyboard():
    keyboard = []
    for cat in CATEGORIES.keys():
        desc = CATEGORY_DESCRIPTIONS.get(cat, "")
        if desc:
            keyboard.append([InlineKeyboardButton(f"{cat}\n{desc}", callback_data=f"cat:{cat}")])
        else:
            keyboard.append([InlineKeyboardButton(f"✨ {cat} ✨", callback_data=f"cat:{cat}")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = build_main_keyboard()
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

    if category == "ورود به کانال ویترین":
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back:main")]]
        await query.edit_message_text(CAT_VITRIN_CHANNEL, reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CATEGORY

    if category == "ورود به کانال حیاط خلوت":
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back:main")]]
        await query.edit_message_text(CAT_HAYAT_CHANNEL, reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CATEGORY

    if category == "ثبت پیام در ویترین":
        subcats = CATEGORIES.get(category, [])
        keyboard = []
        for label, code in subcats:
            keyboard.append([InlineKeyboardButton(label, callback_data=f"vsub:{code}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back:main")])
        await query.edit_message_text(CAT_VITRIN_POST, reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_SUBCATEGORY

    if category == "ثبت پیام در حیاط خلوت":
        subcats = CATEGORIES.get(category, [])
        keyboard = []
        for label, code in subcats:
            keyboard.append([InlineKeyboardButton(label, callback_data=f"sub:{code}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back:main")])
        await query.edit_message_text(CAT_HAYAT_POST, reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_SUBCATEGORY

    return SELECT_CATEGORY

async def select_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back:main":
        await query.edit_message_text(WELCOME, reply_markup=build_main_keyboard())
        return SELECT_CATEGORY

    if query.data.startswith("vsub:"):
        subcode = query.data.replace("vsub:", "")
        sublabel = SUBCAT_LABELS.get(subcode, subcode)
        context.user_data['vitrin_section'] = subcode
        context.user_data['vitrin_section_label'] = sublabel
        category = context.user_data.get('category', '')

        if subcode in SUPPORT_SUBCATS:
            text = """پشتیبانی

پیام خود را بنویسید.
تیم ویترین در اسرع وقت پاسخ خواهد داد ✨

📝 پیام خود را بنویسید:"""
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
            context.user_data['subcategory'] = subcode
            context.user_data['subcategory_label'] = sublabel
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return WRITE_MESSAGE

        if subcode in COMING_SOON_SUBCATS:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
            await query.edit_message_text(COMING_SOON, reply_markup=InlineKeyboardMarkup(keyboard))
            return SELECT_SUBCATEGORY

        if subcode in VITRIN_MAIN_SUBCATS:
            subs = VITRIN_SUBCATS.get(subcode, [])
            vitrin_texts = {
                "sub_work_main": CAT_WORK,
                "sub_house_main": CAT_HOUSING,
                "sub_shop_main": CAT_SHOP,
                "sub_srv_main": CAT_SERVICES,
                "sub_inv_main": CAT_INVESTMENT,
                "sub_euro_main": CAT_EURO,
                "sub_ads_main": CAT_ADS,
            }
            text = vitrin_texts.get(subcode, "زیربخش موردنظر را انتخاب کنید:")
            keyboard = []
            for label, code in subs:
                keyboard.append([InlineKeyboardButton(label, callback_data=f"sub:{code}")])
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return SELECT_VITRIN_SUB

    if query.data.startswith("sub:"):
        subcode = query.data.replace("sub:", "")
        sublabel = SUBCAT_LABELS.get(subcode, subcode)
        context.user_data['subcategory'] = subcode
        context.user_data['subcategory_label'] = sublabel
        category = context.user_data.get('category', '')

        if subcode in COMING_SOON_SUBCATS:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
            await query.edit_message_text(COMING_SOON, reply_markup=InlineKeyboardMarkup(keyboard))
            return SELECT_SUBCATEGORY

        if subcode in HAYAT_MAIN_SUBCATS:
            context.user_data['hayat_type'] = subcode
            context.user_data['hayat_type_label'] = sublabel
            keyboard = []
            for topic in HAYAT_SUBCATS:
                keyboard.append([InlineKeyboardButton(topic, callback_data=f"htopic:{topic}")])
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")])

            type_texts = {
                "sub_hayat_anon": SUB_ANONYMOUS,
                "sub_hayat_exp": SUB_EXPERIENCES,
                "sub_hayat_event": SUB_DORHAM,
                "sub_hayat_news": SUB_NEWS,
            }
            text = type_texts.get(subcode, "موضوع را انتخاب کنید:")
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return SELECT_HAYAT_TOPIC

    return SELECT_SUBCATEGORY

async def select_vitrin_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = context.user_data.get('category', '')
    vitrin_section = context.user_data.get('vitrin_section', '')

    if query.data == "back:main":
        await query.edit_message_text(WELCOME, reply_markup=build_main_keyboard())
        return SELECT_CATEGORY

    if query.data.startswith("cat:"):
        return await select_category(update, context)

    if query.data.startswith("vsub:"):
        return await select_subcategory(update, context)

    if query.data.startswith("sub:"):
        subcode = query.data.replace("sub:", "")
        sublabel = SUBCAT_LABELS.get(subcode, subcode)
        context.user_data['subcategory'] = subcode
        context.user_data['subcategory_label'] = sublabel

        if subcode in COMING_SOON_SUBCATS:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"vsub:{vitrin_section}")]]
            await query.edit_message_text(COMING_SOON, reply_markup=InlineKeyboardMarkup(keyboard))
            return SELECT_VITRIN_SUB

        text = SUBCATEGORY_TEXTS.get(subcode, "📝 پیام خود را بنویسید:")
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"vsub:{vitrin_section}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return WRITE_MESSAGE

    return SELECT_VITRIN_SUB

async def select_hayat_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back:main":
        await query.edit_message_text(WELCOME, reply_markup=build_main_keyboard())
        return SELECT_CATEGORY

    if query.data.startswith("cat:"):
        return await select_category(update, context)

    if query.data.startswith("sub:"):
        return await select_subcategory(update, context)

    topic = query.data.replace("htopic:", "")
    context.user_data['experience'] = topic
    hayat_type = context.user_data.get('hayat_type', 'sub_hayat_exp')
    hayat_label = context.user_data.get('hayat_type_label', '🧭 تجربه‌ها')

    is_dorham = hayat_type == "sub_hayat_event"

    if is_dorham:
        text = f"""دورهمی — {topic}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند ✨

📝 پیام خود را بنویسید:"""
    else:
        text = f"""{hayat_label} — {topic}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند ✨

📝 پیام خود را بنویسید:"""

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"sub:{hayat_type}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
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

    keyboard = [[
        InlineKeyboardButton("✅ تأیید و ارسال", callback_data="confirm:yes"),
        InlineKeyboardButton("✏️ ویرایش", callback_data="confirm:edit"),
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM_MESSAGE

async def confirm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm:edit":
        subcode = context.user_data.get('subcategory', '')
        experience = context.user_data.get('experience', '')
        hayat_label = context.user_data.get('hayat_type_label', '')
        category = context.user_data.get('category', '')
        vitrin_section = context.user_data.get('vitrin_section', '')

        if experience and subcode in HAYAT_MAIN_SUBCATS:
            is_dorham = subcode == "sub_hayat_event"
            if is_dorham:
                text = f"""دورهمی — {experience}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند ✨

📝 پیام خود را بنویسید:"""
            else:
                text = f"""{hayat_label} — {experience}

پیام خود را بنویسید.

⚠️ ارسال عکس، لینک، فیلم، شماره تماس و آیدی مجاز نیست.
هویت شما کاملاً محفوظ می‌ماند ✨

📝 پیام خود را بنویسید:"""
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"sub:{subcode}")]]
        elif subcode in SUPPORT_SUBCATS:
            text = """پشتیبانی

📝 پیام خود را بنویسید:"""
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:{category}")]]
        else:
            text = SUBCATEGORY_TEXTS.get(subcode, "📝 پیام خود را بنویسید:")
            back_target = f"vsub:{vitrin_section}" if vitrin_section else f"cat:{category}"
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data=back_target)]]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
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

        if is_support:
            support_text = f"""📩 پیام پشتیبانی جدید

👤 کاربر: {f"@{user.username}" if user.username else user.full_name}
🆔 آی‌دی: {user.id}

📝 پیام:
━━━━━━━━━━━━━━━
{message}
━━━━━━━━━━━━━━━"""
            await context.bot.send_message(chat_id=ADMIN_ID, text=support_text)
            await query.edit_message_text("✅ پیام شما به تیم پشتیبانی ارسال شد.\n\nدر اسرع وقت پاسخ خواهیم داد ✨")
            return ConversationHandler.END

        admin_text = ADMIN_NEW_POST.format(
            user_name=user_name,
            user_id=user.id if not is_anonymous else "ناشناس",
            category=category,
            subcategory=display_sub,
            message=message
        )

        keyboard_admin = [[
            InlineKeyboardButton("✅ تأیید", callback_data=f"admin:approve:{user.id}"),
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"admin:edit:{user.id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin:reject:{user.id}"),
        ]]

        target_channel = CATEGORY_CHANNELS.get(category, DEFAULT_CHANNEL)

        context.bot_data[f"post_{user.id}"] = {
            'category': category,
            'subcategory': display_sub,
            'message': message,
            'user_name': user_name,
            'is_anonymous': is_anonymous,
            'target_channel': target_channel,
        }

        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=InlineKeyboardMarkup(keyboard_admin))
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
        context.bot_data[f"waiting_edit_{user_id}"] = {'action': 'edit', 'user_id': user_id}
        await query.edit_message_text(query.message.text + "\n\n⏳ دلیل ویرایش را بنویسید...")
        await context.bot.send_message(chat_id=ADMIN_ID, text=ADMIN_ASK_REASON.format(action="ویرایش"))

    elif action == "reject":
        context.bot_data[f"waiting_edit_{user_id}"] = {'action': 'reject', 'user_id': user_id}
        await query.edit_message_text(query.message.text + "\n\n⏳ دلیل رد را بنویسید...")
        await context.bot.send_message(chat_id=ADMIN_ID, text=ADMIN_ASK_REASON.format(action="رد"))

async def admin_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    waiting = None
    waiting_key = None
    for key, val in context.bot_data.items():
        if key.startswith("waiting_edit_"):
            waiting = val
            waiting_key = key
            break

    if not waiting:
        return

    reason = update.message.text
    action = waiting['action']
    user_id = waiting['user_id']

    if action == "edit":
        edit_text = FORM_NEEDS_EDIT.format(reason=reason)
        keyboard = [[InlineKeyboardButton("✏️ ویرایش پیام", callback_data="restart:edit")]]
        await context.bot.send_message(
            chat_id=user_id,
            text=edit_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ پیام ویرایش به کاربر ارسال شد.")
    elif action == "reject":
        await context.bot.send_message(chat_id=user_id, text=FORM_REJECTED.format(reason=reason))
        await update.message.reply_text("✅ پیام رد به کاربر ارسال شد.")

    del context.bot_data[waiting_key]

async def restart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(WELCOME, reply_markup=build_main_keyboard())
    return SELECT_CATEGORY

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(restart_handler, pattern="^restart:"),
        ],
        states={
            SELECT_CATEGORY: [
                CallbackQueryHandler(select_category, pattern="^cat:"),
                CallbackQueryHandler(select_subcategory, pattern="^back:"),
                CallbackQueryHandler(restart_handler, pattern="^restart:"),
            ],
            SELECT_SUBCATEGORY: [
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
                CallbackQueryHandler(select_subcategory, pattern="^vsub:"),
                CallbackQueryHandler(select_subcategory, pattern="^back:"),
                CallbackQueryHandler(select_category, pattern="^cat:"),
                CallbackQueryHandler(restart_handler, pattern="^restart:"),
            ],
            SELECT_VITRIN_SUB: [
                CallbackQueryHandler(select_vitrin_sub, pattern="^sub:"),
                CallbackQueryHandler(select_vitrin_sub, pattern="^vsub:"),
                CallbackQueryHandler(select_vitrin_sub, pattern="^back:"),
                CallbackQueryHandler(select_category, pattern="^cat:"),
                CallbackQueryHandler(restart_handler, pattern="^restart:"),
            ],
            SELECT_HAYAT_TOPIC: [
                CallbackQueryHandler(select_hayat_topic, pattern="^htopic:"),
                CallbackQueryHandler(select_hayat_topic, pattern="^sub:"),
                CallbackQueryHandler(select_hayat_topic, pattern="^cat:"),
                CallbackQueryHandler(select_hayat_topic, pattern="^back:"),
                CallbackQueryHandler(restart_handler, pattern="^restart:"),
            ],
            WRITE_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                CallbackQueryHandler(select_category, pattern="^cat:"),
                CallbackQueryHandler(select_subcategory, pattern="^sub:"),
                CallbackQueryHandler(select_subcategory, pattern="^vsub:"),
                CallbackQueryHandler(select_vitrin_sub, pattern="^back:"),
                CallbackQueryHandler(select_hayat_topic, pattern="^htopic:"),
                CallbackQueryHandler(restart_handler, pattern="^restart:"),
            ],
            CONFIRM_MESSAGE: [
                CallbackQueryHandler(confirm_message, pattern="^confirm:"),
                CallbackQueryHandler(restart_handler, pattern="^restart:"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(restart_handler, pattern="^restart:"),
        ],
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
