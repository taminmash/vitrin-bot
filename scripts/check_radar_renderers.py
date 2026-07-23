from datetime import datetime, timedelta
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def install_import_stubs():
    telegram = types.ModuleType("telegram")

    class InlineKeyboardButton:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class InlineKeyboardMarkup:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class Update:
        pass

    telegram.InlineKeyboardButton = InlineKeyboardButton
    telegram.InlineKeyboardMarkup = InlineKeyboardMarkup
    telegram.Update = Update

    telegram_error = types.ModuleType("telegram.error")
    telegram_error.TelegramError = Exception

    telegram_ext = types.ModuleType("telegram.ext")

    class ContextTypes:
        DEFAULT_TYPE = object

    telegram_ext.ContextTypes = ContextTypes

    database = types.ModuleType("database")
    database_db = types.ModuleType("database.db")
    for name in (
        "count_available_radar_by_type",
        "count_radar_reactions",
        "get_active_radar_item",
        "get_radar_item",
        "list_available_radar_items",
        "save_radar_reaction",
    ):
        setattr(database_db, name, lambda *args, **kwargs: {})

    handlers_start = types.ModuleType("handlers.start")
    handlers_start.MAIN_MENU = None

    async def send_home_dashboard(*args, **kwargs):
        return None

    handlers_start.send_home_dashboard = send_home_dashboard

    sys.modules.setdefault("telegram", telegram)
    sys.modules.setdefault("telegram.error", telegram_error)
    sys.modules.setdefault("telegram.ext", telegram_ext)
    sys.modules.setdefault("database", database)
    sys.modules.setdefault("database.db", database_db)
    sys.modules.setdefault("handlers.start", handlers_start)


install_import_stubs()

from handlers.radar import (
    format_radar_admin_preview,
    format_radar_bot_overview,
    format_radar_channel_post,
    format_radar_details,
)


def sample_item():
    today = datetime(2026, 7, 13)
    return {
        "id": 999,
        "title": "عنوان تست",
        "summary": "این خلاصه باید مستقیم زیر عنوان دیده شود.",
        "ai_reason": "این بخش توضیح می‌دهد چرا خبر مهم است.",
        "body": "این متن کامل فقط در صفحه جزئیات و پیش‌نمایش ادمین نمایش داده می‌شود.",
        "type": "alert",
        "city": "کل اسپانیا",
        "province": "Spain",
        "country": "Spain",
        "start_date": today,
        "end_date": today + timedelta(days=7),
        "source_url": "https://example.com",
        "source_name": "Example",
        "urgency": "high",
        "audience_tags": ["all"],
        "admin_status": "ready",
    }


def assert_contains_in_order(text, parts):
    position = -1
    for part in parts:
        next_position = text.find(part)
        assert next_position > position, f"{part!r} was not found in expected order"
        position = next_position


def main():
    item = sample_item()
    channel = format_radar_channel_post(item)
    overview = format_radar_bot_overview(item)
    details = format_radar_details(item)
    admin = format_radar_admin_preview(item)

    expected_order = [
        "🛰️ رادار اسپانیا",
        "🔥 عنوان تست",
        "━━━━━━━━━━━━━━━━━━",
        "📝 خلاصه",
        item["summary"],
        "💡 چرا مهم است؟",
        item["ai_reason"],
    ]
    for text in (channel, overview, details, admin):
        assert_contains_in_order(text, expected_order)

    assert "📍 محدوده: کل اسپانیا" in details
    assert "Spain / کل اسپانیا / Spain" not in details
    assert "⚡ فوریت: مهم" in details
    assert "وضعیت: آماده انتشار" in admin

    assert item["body"] not in channel
    assert item["source_url"] not in channel
    assert item["source_name"] in channel

    assert item["body"] in details
    assert item["source_url"] in details
    assert item["body"] in admin
    assert item["source_url"] in admin

    print("Radar renderer checks passed")


if __name__ == "__main__":
    main()
