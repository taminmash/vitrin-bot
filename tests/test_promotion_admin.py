import unittest
import importlib.util
from unittest.mock import AsyncMock, Mock, patch

HAS_TELEGRAM = importlib.util.find_spec("telegram") is not None
if HAS_TELEGRAM:
    from handlers.admin import admin_radar_callback
else:
    admin_radar_callback = None
from radar_engine.promotion.models import PromotionResult
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


class FakeUpdate:
    def __init__(self, data):
        self.callback_query = FakeQuery(data)


class FakeContext:
    def __init__(self):
        self.user_data = {}


@unittest.skipUnless(HAS_TELEGRAM, "python-telegram-bot is not installed in this test runtime")
class PromotionAdminTests(unittest.IsolatedAsyncioTestCase):
    async def test_approve_shows_explicit_promotion_action(self):
        update = FakeUpdate("admin_radar:review:approve:candidate-1")
        with patch("handlers.admin.is_admin", return_value=True), patch(
            "handlers.admin.approve_candidate", return_value=True
        ), patch("handlers.admin.publish_radar_item") as publish:
            await admin_radar_callback(update, FakeContext())
        publish.assert_not_called()
        markup = update.callback_query.edit_message_text.call_args.kwargs["reply_markup"]
        callbacks = [
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
            if getattr(button, "callback_data", None)
        ]
        self.assertIn("admin_radar:promote:candidate-1", callbacks)

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
