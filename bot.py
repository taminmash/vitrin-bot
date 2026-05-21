#!/usr/bin/env python3
# ===================================================
# بات ویترین اسپانیا
# ===================================================

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_ID, CATEGORIES
from texts import *

# تنظیم لاگ (ثبت خطاها)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مراحل مکالمه
SELECT_CATEGORY, SELECT_SUBCATEGORY, WRITE_MESSAGE, CONFIRM_MESSAGE = range(4)
ADMIN_REASON = 10

# ===================================================
# دستور /start - شروع بات
# ===================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    cats = list(CATEGORIES.keys())
    
    # دو تا دو تا کنار هم
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(cats[i], callback_data=f"cat:{cats[i]}")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(cats[i+1], callback_data=f"cat:{cats[i+1]}"))
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(WELCOME, reply_markup=reply_markup)
    return SELECT_CATEGORY

# ===================================================
# انتخاب دسته‌بندی
# ===================================================
async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("cat:", "")
    context.user_data['category'] = category
    
    subcats = CATEGORIES.get(category, [])
    
    # اگه زیرمجموعه نداشت مستقیم بره به فرم
    if not subcats:
        if category == "💬 پشتیبانی":
            await query.edit_message_text(CAT_SUPPORT)
            return WRITE_MESSAGE
        elif category == "📢 تبلیغات ویژه":
            await query.edit_message_text(CAT_ADS)
            return SELECT_CATEGORY
    
    # نمایش زیرمجموعه‌ها
    keyboard = []
    for sub in subcats:
        keyboard.append([InlineKeyboardButton(sub, callback_data=f"sub:{sub}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back:main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # متن مناسب هر دسته
    cat_texts = {
        "💼 کار و درآمد": CAT_WORK,
        "🏠 خانه‌یابی": CAT_HOUSING,
        "🛒 خرید و فروش": CAT_SHOP,
        "🔧 خدمات و ارتباطات": CAT_SERVICES,
        "✈️ مهاجرت و زندگی در اسپانیا": CAT_MIGRATION,
        "💰 سرمایه و وام": CAT_INVESTMENT,
        "🏛 جامعه فارسی‌زبانان اسپانیا": CAT_COMMUNITY,
    }
    
    text = cat_texts.get(category, f"بخش {category}\n\n👇 زیربخش موردنظر را انتخاب کنید:")
    await query.edit_message_text(text, reply_markup=reply_markup)
    return SELECT_SUBCATEGORY

# ===================================================
# انتخاب زیرمجموعه
# ===================================================
async def select_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back:main":
        # برگشت به منوی اصلی
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
    
    text = FORM_START.format(category=category, subcategory=subcategory)
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back:cat")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    return WRITE_MESSAGE

# ===================================================
# دریافت پیام از کاربر
# ===================================================
async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    context.user_data['message'] = user_message
    
    category = context.user_data.get('category', '')
    subcategory = context.user_data.get('subcategory', '')
    
    text = FORM_CONFIRM.format(
        message=user_message,
        category=category,
        subcategory=subcategory
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

# ===================================================
# تأیید نهایی کاربر
# ===================================================
async def confirm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm:edit":
        category = context.user_data.get('category', '')
        subcategory = context.user_data.get('subcategory', '')
        text = FORM_START.format(category=category, subcategory=subcategory)
        await query.edit_message_text(text)
        return WRITE_MESSAGE
    
    if query.data == "confirm:yes":
        user = query.from_user
        category = context.user_data.get('category', '')
        subcategory = context.user_data.get('subcategory', '')
        message = context.user_data.get('message', '')
        
        user_name = f"@{user.username}" if user.username else user.full_name
        
        # ارسال به ادمین
        admin_text = ADMIN_NEW_POST.format(
            user_name=user_name,
            user_id=user.id,
            category=category,
            subcategory=subcategory,
            message=message
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=f"admin:approve:{user.id}"),
                InlineKeyboardButton("✏️ نیاز به ویرایش", callback_data=f"admin:edit:{user.id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"admin:reject:{user.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ذخیره پیام برای ارسال به کانال
        context.bot_data[f"post_{user.id}"] = {
            'category': category,
            'subcategory': subcategory,
            'message': message,
            'user_name': user_name,
        }
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=reply_markup
        )
        
        await query.edit_message_text(FORM_SUBMITTED)
        return ConversationHandler.END

# ===================================================
# پنل ادمین - تأیید/رد/ویرایش
# ===================================================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ شما ادمین نیستید!", show_alert=True)
        return
    
    parts = query.data.split(":")
    action = parts[1]
    user_id = int(parts[2])
    
    if action == "approve":
        post = context.bot_data.get(f"post_{user_id}", {})
        
        channel_text = f"""📌 {post.get('category')} | {post.get('subcategory')}

{post.get('message')}

━━━━━━━━━━━━━━━
👤 {post.get('user_name')}
🤖 @VitrinSpainBot"""
        
        await context.bot.send_message(chat_id=CHANNEL_ID, text=channel_text)
        await context.bot.send_message(chat_id=user_id, text=FORM_APPROVED)
        await query.edit_message_text(f"✅ تأیید شد و در کانال منتشر شد.\n\n{query.message.text}")
    
    elif action == "edit":
        context.bot_data[f"waiting_reason_{ADMIN_ID}"] = {'action': 'edit', 'user_id': user_id}
        await query.edit_message_text(
            query.message.text + "\n\n⏳ در حال انتظار برای دلیل ویرایش..."
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=ADMIN_ASK_REASON.format(action="ویرایش")
        )
    
    elif action == "reject":
        context.bot_data[f"waiting_reason_{ADMIN_ID}"] = {'action': 'reject', 'user_id': user_id}
        await query.edit_message_text(
            query.message.text + "\n\n⏳ در حال انتظار برای دلیل رد..."
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=ADMIN_ASK_REASON.format(action="رد")
        )

# ===================================================
# دریافت دلیل از ادمین
# ===================================================
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
        await context.bot.send_message(
            chat_id=user_id,
            text=FORM_NEEDS_EDIT.format(reason=reason)
        )
        await update.message.reply_text("✅ پیام ویرایش به کاربر ارسال شد.")
    
    elif action == "reject":
        await context.bot.send_message(
            chat_id=user_id,
            text=FORM_REJECTED.format(reason=reason)
        )
        await update.message.reply_text("✅ پیام رد به کاربر ارسال شد.")
    
    del context.bot_data[f"waiting_reason_{ADMIN_ID}"]

# ===================================================
# اجرای بات
# ===================================================
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
            ],
            WRITE_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
                CallbackQueryHandler(select_category, pattern="^back:cat"),
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
