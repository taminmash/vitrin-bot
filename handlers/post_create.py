from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from config_v2 import (
    ADMIN_ID,
    BACK_BUTTON,
    CATEGORIES,
    POST_STATUS_DELETED,
    POST_STATUS_NEEDS_EDIT,
    POST_STATUS_PENDING,
    POST_STATUS_PUBLISHED,
    STATUS_LABELS,
    SUBCATEGORIES,
)
from database.db import (
    create_post,
    delete_post,
    get_post,
    get_user,
    update_post_content,
    upsert_user,
)
from handlers.common import admin_keyboard, admin_post_text, back_keyboard, list_keyboard, user_manage_keyboard


STATE_CATEGORY = "category"
STATE_SUBCATEGORY = "subcategory"
STATE_NAME = "name"
STATE_CITY = "city"
STATE_CONTENT = "content"
STATE_EDIT_CONTENT = "edit_content"


def reset_flow(context):
    context.user_data.pop("state", None)
    context.user_data.pop("category", None)
    context.user_data.pop("subcategory", None)
    context.user_data.pop("name", None)
    context.user_data.pop("city", None)
    context.user_data.pop("editing_post_id", None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_flow(context)
    context.user_data["state"] = STATE_CATEGORY
    await update.message.reply_text(
        "لطفاً دسته اصلی آگهی را انتخاب کنید.",
        reply_markup=list_keyboard(CATEGORIES),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_flow(context)
    await update.message.reply_text(
        "عملیات لغو شد.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get("state")

    if not state:
        await start(update, context)
        return

    if text == BACK_BUTTON:
        await go_back(update, context)
        return

    if state == STATE_CATEGORY:
        await handle_category(update, context, text)
        return

    if state == STATE_SUBCATEGORY:
        await handle_subcategory(update, context, text)
        return

    if state == STATE_NAME:
        await handle_name(update, context, text)
        return

    if state == STATE_CITY:
        await handle_city(update, context, text)
        return

    if state == STATE_CONTENT:
        await handle_content(update, context, text)
        return

    if state == STATE_EDIT_CONTENT:
        await handle_edit_content(update, context, text)
        return

    await start(update, context)


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if state == STATE_CATEGORY:
        await update.message.reply_text(
            "شما در مرحله انتخاب دسته هستید.",
            reply_markup=list_keyboard(CATEGORIES),
        )
        return

    if state == STATE_SUBCATEGORY:
        context.user_data["state"] = STATE_CATEGORY
        await update.message.reply_text(
            "لطفاً دسته اصلی آگهی را انتخاب کنید.",
            reply_markup=list_keyboard(CATEGORIES),
        )
        return

    if state == STATE_NAME:
        context.user_data["state"] = STATE_SUBCATEGORY
        category = context.user_data.get("category")
        await update.message.reply_text(
            "لطفاً ساب‌دسته آگهی را انتخاب کنید.",
            reply_markup=list_keyboard(SUBCATEGORIES.get(category, [])),
        )
        return

    if state == STATE_CITY:
        context.user_data["state"] = STATE_NAME
        await update.message.reply_text(
            "لطفاً نام خود را وارد کنید.",
            reply_markup=back_keyboard(),
        )
        return

    if state == STATE_CONTENT:
        user = get_user(update.effective_user.id)
        if user:
            context.user_data["state"] = STATE_SUBCATEGORY
            category = context.user_data.get("category")
            await update.message.reply_text(
                "لطفاً ساب‌دسته آگهی را انتخاب کنید.",
                reply_markup=list_keyboard(SUBCATEGORIES.get(category, [])),
            )
        else:
            context.user_data["state"] = STATE_CITY
            await update.message.reply_text(
                "لطفاً شهر خود را وارد کنید.",
                reply_markup=back_keyboard(),
            )
        return

    if state == STATE_EDIT_CONTENT:
        post_id = context.user_data.get("editing_post_id")
        reset_flow(context)
        await update.message.reply_text(
            "ویرایش لغو شد.",
            reply_markup=ReplyKeyboardRemove(),
        )
        if post_id:
            await update.message.reply_text(
                "پنل مدیریت آگهی:",
                reply_markup=user_manage_keyboard(post_id),
            )
        return


async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if text not in CATEGORIES:
        await update.message.reply_text(
            "لطفاً یکی از دسته‌های موجود را انتخاب کنید.",
            reply_markup=list_keyboard(CATEGORIES),
        )
        return

    context.user_data["category"] = text
    context.user_data["state"] = STATE_SUBCATEGORY
    await update.message.reply_text(
        "لطفاً ساب‌دسته آگهی را انتخاب کنید.",
        reply_markup=list_keyboard(SUBCATEGORIES.get(text, [])),
    )


async def handle_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    category = context.user_data.get("category")
    subcategories = SUBCATEGORIES.get(category, [])

    if text not in subcategories:
        await update.message.reply_text(
            "لطفاً یکی از ساب‌دسته‌های موجود را انتخاب کنید.",
            reply_markup=list_keyboard(subcategories),
        )
        return

    context.user_data["subcategory"] = text

    user = get_user(update.effective_user.id)
    if user and user.get("city"):
        context.user_data["name"] = user.get("full_name")
        context.user_data["city"] = user.get("city")
        context.user_data["state"] = STATE_CONTENT
        await update.message.reply_text(
            "لطفاً متن آگهی را ارسال کنید.",
            reply_markup=back_keyboard(),
        )
        return

    context.user_data["state"] = STATE_NAME
    await update.message.reply_text(
        "لطفاً نام خود را وارد کنید.",
        reply_markup=back_keyboard(),
    )


async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    context.user_data["name"] = text
    context.user_data["state"] = STATE_CITY
    await update.message.reply_text(
        "لطفاً شهر خود را وارد کنید.",
        reply_markup=back_keyboard(),
    )


async def handle_city(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    context.user_data["city"] = text
    tg_user = update.effective_user

    upsert_user(
        telegram_id=tg_user.id,
        full_name=context.user_data.get("name") or tg_user.full_name,
        username=tg_user.username,
        city=text,
    )

    context.user_data["state"] = STATE_CONTENT
    await update.message.reply_text(
        "لطفاً متن آگهی را ارسال کنید.",
        reply_markup=back_keyboard(),
    )


async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    tg_user = update.effective_user
    user = get_user(tg_user.id)

    if not user:
        upsert_user(
            telegram_id=tg_user.id,
            full_name=tg_user.full_name,
            username=tg_user.username,
            city=context.user_data.get("city"),
        )
        user = get_user(tg_user.id)

    post = create_post(
        telegram_id=tg_user.id,
        category=context.user_data["category"],
        subcategory=context.user_data["subcategory"],
        content=text,
        city=user.get("city"),
    )

    reset_flow(context)

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_post_text(post),
        reply_markup=admin_keyboard(post["id"]),
    )

    await update.message.reply_text(
        "آگهی شما ثبت شد و برای بررسی به ادمین ارسال شد.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        "پنل مدیریت آگهی:",
        reply_markup=user_manage_keyboard(post["id"]),
    )


async def user_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    action = parts[1]
    post_id = int(parts[2])

    post = get_post(post_id)
    if not post:
        await query.message.reply_text("آگهی پیدا نشد.")
        return

    if post["telegram_id"] != query.from_user.id:
        await query.message.reply_text("این آگهی متعلق به شما نیست.")
        return

    if action == "status":
        await query.message.reply_text(STATUS_LABELS.get(post["status"], post["status"]))
        return

    if action == "edit":
        if post["status"] == POST_STATUS_PUBLISHED:
            await query.message.reply_text("این آگهی منتشر شده و قابل ویرایش نیست.")
            return

        if post["status"] == POST_STATUS_DELETED:
            await query.message.reply_text("این آگهی حذف شده و قابل ویرایش نیست.")
            return

        context.user_data["state"] = STATE_EDIT_CONTENT
        context.user_data["editing_post_id"] = post_id
        await query.message.reply_text(
            "📝 لطفاً پیام خود را ویرایش کرده و مجدداً ارسال نمایید.",
            reply_markup=back_keyboard(),
        )
        return

    if action == "delete":
        if post["status"] == POST_STATUS_PUBLISHED:
            await query.message.reply_text("این آگهی منتشر شده و از این پنل قابل حذف نیست.")
            return

        if post["status"] == POST_STATUS_DELETED:
            await query.message.reply_text("این آگهی قبلاً حذف شده است.")
            return

        post = delete_post(post_id)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🗑️ کاربر آگهی زیر را حذف کرد:\n\n{admin_post_text(post)}",
        )
        await query.message.reply_text("🗑️ آگهی شما حذف شد.")
        return


async def handle_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    post_id = context.user_data.get("editing_post_id")
    if not post_id:
        reset_flow(context)
        await update.message.reply_text(
            "آگهی برای ویرایش پیدا نشد.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    post = get_post(post_id)
    if not post:
        reset_flow(context)
        await update.message.reply_text(
            "آگهی پیدا نشد.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if post["telegram_id"] != update.effective_user.id:
        reset_flow(context)
        await update.message.reply_text(
            "این آگهی متعلق به شما نیست.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if post["status"] in (POST_STATUS_PUBLISHED, POST_STATUS_DELETED):
        reset_flow(context)
        await update.message.reply_text(
            "این آگهی دیگر قابل ویرایش نیست.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    post = update_post_content(post_id, text)
    reset_flow(context)

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_post_text(post),
        reply_markup=admin_keyboard(post["id"]),
    )

    await update.message.reply_text(
        "آگهی ویرایش شد و دوباره برای بررسی به ادمین ارسال شد.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        "پنل مدیریت آگهی:",
        reply_markup=user_manage_keyboard(post["id"]),
    )
