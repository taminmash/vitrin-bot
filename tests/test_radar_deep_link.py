import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.radar import details_keyboard, open_radar_deep_link


class RadarDeepLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_deep_link_opens_exact_full_detail_immediately(self):
        item = {"id": "job-123", "type": "job", "structured_data": {"category": "job"}}
        update = SimpleNamespace(message=object())
        with (
            patch("handlers.radar.get_active_or_demo_radar_item", return_value=item) as loader,
            patch("handlers.radar.send_radar_details_message", new_callable=AsyncMock) as details,
            patch("handlers.radar.send_radar_item_message", new_callable=AsyncMock) as overview,
        ):
            await open_radar_deep_link(update, "job-123")
        loader.assert_called_once_with("job-123")
        details.assert_awaited_once_with(update.message, item)
        overview.assert_not_awaited()

    async def test_non_job_deep_link_keeps_existing_overview_behavior(self):
        item = {"id": "event-123", "type": "event", "structured_data": {}}
        update = SimpleNamespace(message=object())
        with (
            patch("handlers.radar.get_active_or_demo_radar_item", return_value=item),
            patch("handlers.radar.send_radar_details_message", new_callable=AsyncMock) as details,
            patch("handlers.radar.send_radar_item_message", new_callable=AsyncMock) as overview,
        ):
            await open_radar_deep_link(update, "event-123")
        overview.assert_awaited_once_with(update.message, item)
        details.assert_not_awaited()

    async def test_expired_job_deep_link_uses_historical_item(self):
        item = {
            "id": "job-expired", "type": "job", "content_status": "expired",
            "structured_data": {"category": "job", "job_title": "معمار", "deadline": "2020-01-01"},
        }
        update = SimpleNamespace(message=object())
        with (
            patch("handlers.radar.get_active_or_demo_radar_item", return_value=None),
            patch("handlers.radar.get_radar_item", return_value=item) as historical,
            patch("handlers.radar.send_radar_details_message", new_callable=AsyncMock) as details,
        ):
            await open_radar_deep_link(update, "job-expired")
        historical.assert_called_once_with("job-expired")
        details.assert_awaited_once_with(update.message, item)

    def test_job_detail_keyboard_keeps_share_and_standard_navigation(self):
        item = {"id": "job-123", "type": "job", "structured_data": {"category": "job"}}
        with (
            patch("handlers.radar.BOT_USERNAME", "VitrinSpainBot"),
            patch("handlers.radar.CHANNEL_VITRIN_LINK", None),
        ):
            keyboard = details_keyboard(item)
        buttons = [button for row in keyboard.inline_keyboard for button in row]
        self.assertEqual(
            [button.text for button in buttons],
            [
                "↩️ بازگشت به ویترین",
                "📤 اشتراک‌گذاری",
                "🤝 درخواست اقدام توسط ویترین",
                "⬅️ بازگشت به صفحه قبلی",
                "🏠 بازگشت به صفحه اصلی",
            ],
        )
        self.assertEqual(buttons[0].url, "https://t.me/VitrinSpainBot?start=radar_job-123")
        self.assertEqual(buttons[1].switch_inline_query, "https://t.me/VitrinSpainBot?start=radar_job-123")
        self.assertEqual(buttons[2].callback_data, "radar:apply:job-123")
        self.assertEqual(buttons[3].callback_data, "radar:item:job-123")
        self.assertEqual(buttons[4].callback_data, "radar:home")

    def test_expired_job_keyboard_removes_active_share_control(self):
        item = {
            "id": "job-expired", "type": "job", "content_status": "expired",
            "structured_data": {"category": "job", "deadline": "2020-01-01"},
        }
        with (
            patch("handlers.radar.BOT_USERNAME", "VitrinSpainBot"),
            patch("handlers.radar.CHANNEL_VITRIN_LINK", None),
        ):
            keyboard = details_keyboard(item)
        labels = [button.text for row in keyboard.inline_keyboard for button in row]
        self.assertEqual(labels, ["⬅️ بازگشت به صفحه قبلی", "🏠 بازگشت به صفحه اصلی"])
        self.assertNotIn("اشتراک‌گذاری", " ".join(labels))


if __name__ == "__main__":
    unittest.main()
