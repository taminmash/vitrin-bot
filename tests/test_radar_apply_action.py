import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import TelegramError

from handlers.radar import (
    REQUEST_ACTION_UNAVAILABLE_TEXT,
    details_keyboard,
    radar_callback,
    request_action_unavailable_keyboard,
)
from radar_engine.job_expiration import MADRID_TZ, EXPIRED_DETAIL_MESSAGE


def job_item(**overrides):
    item = {
        "id": "job-123",
        "type": "job",
        "content_status": "ready",
        "structured_data": {"category": "job", "job_title": "معمار"},
    }
    item.update(overrides)
    return item


def callback_update(data):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=message,
    )
    return SimpleNamespace(callback_query=query), query


class RadarApplyKeyboardTests(unittest.TestCase):
    def test_active_job_actions_hide_nonfunctional_request_placeholder(self):
        with (
            patch("handlers.radar.BOT_USERNAME", "VitrinSpainBot"),
            patch("handlers.radar.CHANNEL_VITRIN_LINK", "https://t.me/vitrinspain/42"),
        ):
            keyboard = details_keyboard(job_item())
        self.assertTrue(all(len(row) == 1 for row in keyboard.inline_keyboard))
        buttons = [row[0] for row in keyboard.inline_keyboard]
        self.assertEqual(
            [button.text for button in buttons],
            [
                "↩️ بازگشت به کانال ویترین",
                "📤 اشتراک‌گذاری",
                "⬅️ بازگشت به صفحه قبلی",
                "🏠 بازگشت به صفحه اصلی",
            ],
        )
        self.assertEqual(buttons[0].url, "https://t.me/vitrinspain/42")
        self.assertEqual(buttons[1].switch_inline_query, "https://t.me/VitrinSpainBot?start=radar_job-123")
        self.assertNotIn("🤝 درخواست اقدام توسط ویترین", [button.text for button in buttons])
        self.assertEqual(buttons[2].callback_data, "radar:item:job-123")
        self.assertLessEqual(len(buttons[2].callback_data.encode("utf-8")), 64)

    def test_stale_but_active_job_keeps_request_action(self):
        stale = job_item(published_at=datetime.now(MADRID_TZ) - timedelta(days=45))
        labels = [row[0].text for row in details_keyboard(stale).inline_keyboard]
        self.assertNotIn("🤝 درخواست اقدام توسط ویترین", labels)

    def test_expired_job_does_not_show_request_or_share(self):
        expired = job_item(structured_data={"category": "job", "deadline": "2020-01-01"})
        labels = [row[0].text for row in details_keyboard(expired).inline_keyboard]
        self.assertNotIn("🤝 درخواست اقدام توسط ویترین", labels)
        self.assertNotIn("📤 اشتراک‌گذاری", labels)

    def test_placeholder_keyboard_returns_to_exact_job_then_home(self):
        rows = request_action_unavailable_keyboard("job-123").inline_keyboard
        self.assertEqual([len(row) for row in rows], [1, 1])
        self.assertEqual(rows[0][0].text, "⬅️ بازگشت به صفحه قبلی")
        self.assertEqual(rows[0][0].callback_data, "radar:details:job-123")
        self.assertEqual(rows[1][0].text, "🏠 بازگشت به صفحه اصلی")
        self.assertEqual(rows[1][0].callback_data, "radar:home")


class RadarApplyCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_action_opens_exact_placeholder_and_only_reads_item(self):
        update, query = callback_update("radar:apply:job-123")
        context = SimpleNamespace(user_data={})
        with (
            patch("handlers.radar.get_active_or_demo_radar_item", return_value=job_item()) as loader,
            patch("handlers.radar.get_radar_item") as historical,
            patch("handlers.radar.save_radar_reaction") as database_write,
        ):
            await radar_callback(update, context)
        query.answer.assert_awaited_once_with()
        loader.assert_called_once_with("job-123")
        historical.assert_not_called()
        database_write.assert_not_called()
        query.edit_message_text.assert_awaited_once()
        kwargs = query.edit_message_text.await_args.kwargs
        self.assertEqual(query.edit_message_text.await_args.args[0], REQUEST_ACTION_UNAVAILABLE_TEXT)
        self.assertEqual(
            [[button.callback_data for button in row] for row in kwargs["reply_markup"].inline_keyboard],
            [["radar:details:job-123"], ["radar:home"]],
        )

    async def test_job_expired_between_render_and_click_shows_expired_detail(self):
        update, query = callback_update("radar:apply:job-123")
        expired = job_item(structured_data={"category": "job", "job_title": "معمار", "deadline": "2020-01-01"})
        with patch("handlers.radar.get_active_or_demo_radar_item", return_value=expired):
            await radar_callback(update, SimpleNamespace(user_data={}))
        query.answer.assert_awaited_once_with()
        text = query.edit_message_text.await_args.args[0]
        self.assertTrue(text.startswith(EXPIRED_DETAIL_MESSAGE))
        labels = [row[0].text for row in query.edit_message_text.await_args.kwargs["reply_markup"].inline_keyboard]
        self.assertNotIn("🤝 درخواست اقدام توسط ویترین", labels)

    async def test_malformed_or_missing_job_is_handled_and_answered(self):
        for data in ("radar:apply", "radar:apply:", "radar:apply:missing:extra"):
            with self.subTest(data=data):
                update, query = callback_update(data)
                with (
                    patch("handlers.radar.get_active_or_demo_radar_item", return_value=None),
                    patch("handlers.radar.get_radar_item", return_value=None),
                ):
                    await radar_callback(update, SimpleNamespace(user_data={}))
                query.answer.assert_awaited_once_with()
                self.assertEqual(query.edit_message_text.await_args.args[0], "این آگهی شغلی پیدا نشد.")

    async def test_edit_failure_sends_fallback_message(self):
        update, query = callback_update("radar:apply:job-123")
        query.edit_message_text.side_effect = TelegramError("message is not editable")
        with patch("handlers.radar.get_active_or_demo_radar_item", return_value=job_item()):
            await radar_callback(update, SimpleNamespace(user_data={}))
        query.answer.assert_awaited_once_with()
        query.message.reply_text.assert_awaited_once()
        self.assertEqual(query.message.reply_text.await_args.args[0], REQUEST_ACTION_UNAVAILABLE_TEXT)

    async def test_placeholder_previous_edits_back_to_same_job_detail(self):
        update, query = callback_update("radar:details:job-123")
        with patch("handlers.radar.get_active_or_demo_radar_item", return_value=job_item()):
            await radar_callback(update, SimpleNamespace(user_data={}))
        query.answer.assert_awaited_once_with()
        query.edit_message_text.assert_awaited_once()
        self.assertIn("معمار", query.edit_message_text.await_args.args[0])

    async def test_placeholder_home_uses_existing_main_dashboard(self):
        update, query = callback_update("radar:home")
        context = SimpleNamespace(user_data={"navigation": "job-123"})
        with patch("handlers.radar.send_home_dashboard", new_callable=AsyncMock) as home:
            await radar_callback(update, context)
        query.answer.assert_awaited_once_with()
        home.assert_awaited_once_with(update)
        self.assertEqual(context.user_data, {})


if __name__ == "__main__":
    unittest.main()
