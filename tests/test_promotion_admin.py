import unittest
import importlib.util
from unittest.mock import AsyncMock, Mock, patch

HAS_TELEGRAM = importlib.util.find_spec("telegram") is not None
if HAS_TELEGRAM:
    from handlers.admin import admin_radar_callback, radar_item_preview_keyboard
else:
    admin_radar_callback = None
    radar_item_preview_keyboard = None
from radar_engine.promotion.models import PromotionResult
from radar_engine.publication.models import PublicationResult
from tests.test_promotion_mapper import make_source


class FakeUser:
    id = 123


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.from_user = FakeUser()
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.message = Mock()
        self.message.reply_text = AsyncMock()
        self.edit_message_reply_markup = AsyncMock()


class FakeUpdate:
    def __init__(self, data):
        self.callback_query = FakeQuery(data)


class FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot = Mock()


@unittest.skipUnless(HAS_TELEGRAM, "python-telegram-bot is not installed in this test runtime")
class PromotionAdminTests(unittest.IsolatedAsyncioTestCase):
    def test_ready_queue_item_offers_direct_publish_and_standard_navigation(self):
        markup = radar_item_preview_keyboard(
            {"id": "radar-1", "content_status": "ready", "channel_status": "not_sent"}
        )
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(
            [button.text for button in buttons],
            ["✅ انتشار در ویترین", "⬅️ بازگشت به صفحه قبلی", "🏠 بازگشت به صفحه اصلی"],
        )
        self.assertEqual(buttons[0].callback_data, "admin_radar:publish_confirm:radar-1")

    async def test_approve_shows_direct_four_button_decision_menu(self):
        update = FakeUpdate("admin_radar:review:approve:candidate-1")
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.approve_candidate", return_value=True
        ), patch("handlers.admin.publish_radar_item") as publish:
            await admin_radar_callback(update, FakeContext())
        publish.assert_not_called()
        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(
            [button.text for button in buttons],
            [
                "✅ انتشار در ویترین",
                "⏳ انتقال به انتظار انتشار",
                "⬅️ بازگشت به صفحه قبلی",
                "🏠 بازگشت به صفحه اصلی",
            ],
        )
        self.assertEqual(
            [button.callback_data for button in buttons],
            [
                "admin_radar:r:u:candidate-1",
                "admin_radar:r:p:candidate-1",
                "admin_radar:review:list",
                "admin_radar:menu:home",
            ],
        )

    async def test_promote_action_creates_ready_item_without_publishing(self):
        update = FakeUpdate("admin_radar:promote:candidate-1")
        result = PromotionResult("candidate-1", "created", radar_item_id="radar-1", promotion_id="promotion-1")
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.get_approved_promotion_source", return_value=make_source()
        ), patch("handlers.admin.promote_candidate", return_value=result) as promote, patch(
            "handlers.admin.publish_radar_item"
        ) as publish:
            await admin_radar_callback(update, FakeContext())
        promote.assert_called_once()
        publish.assert_not_called()
        text = update.callback_query.edit_message_text.call_args.args[0]
        self.assertIn("Radar item ID", text)
        self.assertIn("radar-1", text)

    async def test_direct_publish_after_approval_uses_existing_publisher(self):
        update = FakeUpdate("admin_radar:r:u:candidate-1")
        promotion = PromotionResult("candidate-1", "created", radar_item_id="radar-1", promotion_id="promotion-1")
        publication = PublicationResult("radar-1", "published", telegram_message_id=42)
        item = {"id": "radar-1", "content_status": "ready", "channel_status": "not_sent"}
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.get_approved_promotion_source", return_value=make_source()
        ), patch("handlers.admin.promote_candidate", return_value=promotion), patch(
            "handlers.admin.get_radar_item", return_value=item
        ), patch("handlers.admin.is_radar_expired", return_value=False), patch(
            "handlers.admin.publish_radar_item", new=AsyncMock(return_value=publication)
        ) as publish:
            await admin_radar_callback(update, FakeContext())
        publish.assert_awaited_once()
        text = update.callback_query.edit_message_text.call_args.args[0]
        self.assertIn("در کانال منتشر شد", text)

    async def test_expired_direct_publish_is_blocked_without_telegram_call(self):
        update = FakeUpdate("admin_radar:r:u:candidate-1")
        promotion = PromotionResult("candidate-1", "already_promoted", radar_item_id="radar-1", promotion_id="promotion-1")
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.get_approved_promotion_source", return_value=make_source(already_promoted=True)
        ), patch("handlers.admin.promote_candidate", return_value=promotion), patch(
            "handlers.admin.get_radar_item", return_value={"id": "radar-1"}
        ), patch("handlers.admin.is_radar_expired", return_value=True), patch(
            "handlers.admin.publish_radar_item", new=AsyncMock()
        ) as publish:
            await admin_radar_callback(update, FakeContext())
        publish.assert_not_awaited()
        self.assertIn("منقضی", update.callback_query.edit_message_text.call_args.args[0])

    async def test_direct_publish_failure_keeps_approved_item_retryable(self):
        update = FakeUpdate("admin_radar:r:u:candidate-1")
        promotion = PromotionResult("candidate-1", "already_promoted", radar_item_id="radar-1", promotion_id="promotion-1")
        publication = PublicationResult("radar-1", "telegram_failed", error="temporary")
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.get_approved_promotion_source", return_value=make_source(already_promoted=True)
        ), patch("handlers.admin.promote_candidate", return_value=promotion), patch(
            "handlers.admin.get_radar_item", return_value={"id": "radar-1"}
        ), patch("handlers.admin.is_radar_expired", return_value=False), patch(
            "handlers.admin.publish_radar_item", new=AsyncMock(return_value=publication)
        ):
            await admin_radar_callback(update, FakeContext())
        text = update.callback_query.edit_message_text.call_args.args[0]
        self.assertIn("انتشار رادار انجام نشد", text)
        callbacks = [
            button.callback_data
            for row in update.callback_query.edit_message_text.call_args.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        self.assertIn("admin_radar:r:d:candidate-1", callbacks)

    async def test_duplicate_direct_publication_is_reported_without_losing_decision(self):
        update = FakeUpdate("admin_radar:r:u:candidate-1")
        promotion = PromotionResult("candidate-1", "already_promoted", radar_item_id="radar-1", promotion_id="promotion-1")
        publication = PublicationResult("radar-1", "already_published", telegram_message_id=42)
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.get_approved_promotion_source", return_value=make_source(already_promoted=True)
        ), patch("handlers.admin.promote_candidate", return_value=promotion), patch(
            "handlers.admin.get_radar_item", return_value={"id": "radar-1"}
        ), patch("handlers.admin.is_radar_expired", return_value=False), patch(
            "handlers.admin.publish_radar_item", new=AsyncMock(return_value=publication)
        ):
            await admin_radar_callback(update, FakeContext())
        self.assertIn("قبلاً منتشر شده", update.callback_query.edit_message_text.call_args.args[0])

    async def test_home_button_returns_to_main_dashboard_behavior(self):
        update = FakeUpdate("admin_radar:menu:home")
        context = FakeContext()
        with patch("handlers.admin.is_admin", return_value=True):
            await admin_radar_callback(update, context)
        update.callback_query.message.reply_text.assert_awaited_once()
        self.assertEqual(context.user_data, {})

    async def test_duplicate_promote_click_is_safe(self):
        update = FakeUpdate("admin_radar:promote:candidate-1")
        result = PromotionResult("candidate-1", "already_promoted", radar_item_id="radar-1", promotion_id="promotion-1")
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.get_approved_promotion_source", return_value=make_source(already_promoted=True)
        ), patch("handlers.admin.promote_candidate", return_value=result), patch("handlers.admin.publish_radar_item") as publish:
            await admin_radar_callback(update, FakeContext())
        publish.assert_not_called()
        text = update.callback_query.edit_message_text.call_args.args[0]
        self.assertIn("radar-1", text)


if __name__ == "__main__":
    unittest.main()
