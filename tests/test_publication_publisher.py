import unittest
from datetime import datetime, timedelta

from radar_engine.publication.models import EligiblePublicationItem
from radar_engine.publication.publisher import (
    AmbiguousTelegramFailure,
    DefiniteTelegramFailure,
    PublicationValidationError,
    RadarTelegramPublisher,
    build_channel_post_url,
    validate_publication_item,
)


def ready_item(**overrides):
    item = {
        "id": "radar-1",
        "title": "هشدار موج گرما",
        "summary": "خلاصه کوتاه",
        "content_status": "ready",
        "channel_status": "not_sent",
        "is_published": False,
        "channel_message_id": None,
        "expires_at": datetime.now() + timedelta(days=1),
    }
    item.update(overrides)
    return item


class FakeMessage:
    message_id = 321


class FakeBot:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeMessage()


class TimedOut(Exception):
    pass


class PublicationPublisherTests(unittest.IsolatedAsyncioTestCase):
    def test_validation_rejects_non_ready_or_already_sent_items(self):
        errors = validate_publication_item(
            ready_item(content_status="published", is_published=True, channel_message_id=99),
            rendered_text="post",
            channel_id="@vitrin",
        )
        codes = {error["code"] for error in errors}
        self.assertIn("not_ready", codes)
        self.assertIn("already_public", codes)
        self.assertIn("already_sent", codes)

    def test_validation_rejects_expired_blank_or_too_long_posts(self):
        errors = validate_publication_item(
            ready_item(title="", summary="", expires_at=datetime.now() - timedelta(days=1)),
            rendered_text="x" * 4097,
            channel_id="",
        )
        codes = {error["code"] for error in errors}
        self.assertIn("blank_title", codes)
        self.assertIn("blank_summary", codes)
        self.assertIn("expired", codes)
        self.assertIn("missing_channel", codes)
        self.assertIn("too_long", codes)

    def test_channel_post_url_uses_username_when_available(self):
        self.assertEqual(build_channel_post_url("-100123", 5, "vitrinspain"), "https://t.me/vitrinspain/5")
        self.assertEqual(build_channel_post_url("@vitrinspain", 5), "https://t.me/vitrinspain/5")
        self.assertIsNone(build_channel_post_url("-100123", 5))

    async def test_publish_sends_existing_renderer_and_keyboard_once(self):
        bot = FakeBot()
        keyboard = object()
        publisher = RadarTelegramPublisher(
            bot,
            channel_id="@vitrinspain",
            renderer=lambda item: f"📡 {item['title']}",
            keyboard_builder=lambda item: keyboard,
        )
        response = await publisher.publish(EligiblePublicationItem(ready_item()))
        self.assertEqual(response.telegram_message_id, 321)
        self.assertEqual(response.channel_post_url, "https://t.me/vitrinspain/321")
        self.assertEqual(len(bot.calls), 1)
        self.assertEqual(bot.calls[0]["chat_id"], "@vitrinspain")
        self.assertEqual(bot.calls[0]["reply_markup"], keyboard)
        self.assertTrue(bot.calls[0]["disable_web_page_preview"])

    async def test_publish_maps_definite_and_ambiguous_telegram_failures(self):
        definite = RadarTelegramPublisher(
            FakeBot(RuntimeError("bad request")),
            channel_id="@vitrinspain",
            renderer=lambda item: "post",
            keyboard_builder=lambda item: None,
        )
        with self.assertRaises(DefiniteTelegramFailure):
            await definite.publish(EligiblePublicationItem(ready_item()))

        ambiguous = RadarTelegramPublisher(
            FakeBot(TimedOut("network timeout")),
            channel_id="@vitrinspain",
            renderer=lambda item: "post",
            keyboard_builder=lambda item: None,
        )
        with self.assertRaises(AmbiguousTelegramFailure):
            await ambiguous.publish(EligiblePublicationItem(ready_item()))

    async def test_publish_does_not_send_invalid_rendered_post(self):
        bot = FakeBot()
        publisher = RadarTelegramPublisher(
            bot,
            channel_id="@vitrinspain",
            renderer=lambda item: "",
            keyboard_builder=lambda item: None,
        )
        with self.assertRaises(PublicationValidationError):
            await publisher.publish(EligiblePublicationItem(ready_item()))
        self.assertEqual(bot.calls, [])


if __name__ == "__main__":
    unittest.main()
