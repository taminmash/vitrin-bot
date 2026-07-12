import unittest

from radar_engine.publication.engine import RadarPublicationEngine
from radar_engine.publication.models import EligiblePublicationItem, PublicationResult, TelegramPublicationResponse
from radar_engine.publication.publisher import AmbiguousTelegramFailure, DefiniteTelegramFailure
from tests.test_publication_publisher import ready_item


class FakePublisher:
    channel_id = "@vitrinspain"

    def __init__(self, response=None, error=None):
        self.response = response or TelegramPublicationResponse("@vitrinspain", 123)
        self.error = error
        self.sent = []

    async def publish(self, item):
        self.sent.append(item.id)
        if self.error:
            raise self.error
        return self.response


class PublicationEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_publication_records_success(self):
        item = EligiblePublicationItem(ready_item(id="radar-1"))
        successes = []

        def success_recorder(item_id, response, published_by=None):
            successes.append((item_id, response.telegram_message_id, published_by))
            return PublicationResult(item_id, "published", telegram_message_id=response.telegram_message_id)

        publisher = FakePublisher()
        engine = RadarPublicationEngine(
            publisher=publisher,
            success_recorder=success_recorder,
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(item, published_by=77)
        self.assertTrue(result.published)
        self.assertEqual(publisher.sent, ["radar-1"])
        self.assertEqual(successes, [("radar-1", 123, 77)])

    async def test_duplicate_publication_is_blocked_before_send(self):
        publisher = FakePublisher()
        engine = RadarPublicationEngine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_success_loader=lambda item_id: {"telegram_message_id": 55},
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.already_published)
        self.assertEqual(result.telegram_message_id, 55)
        self.assertEqual(publisher.sent, [])

    async def test_existing_channel_message_is_blocked_before_send(self):
        publisher = FakePublisher()
        engine = RadarPublicationEngine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: {"channel_message_id": 56},
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.already_published)
        self.assertEqual(result.telegram_message_id, 56)
        self.assertEqual(publisher.sent, [])

    async def test_dry_run_validates_without_sending_or_persisting(self):
        publisher = FakePublisher()
        engine = RadarPublicationEngine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()), dry_run=True)
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(publisher.sent, [])

    async def test_validation_failure_skips_send(self):
        publisher = FakePublisher()
        engine = RadarPublicationEngine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item(title="")))
        self.assertEqual(result.status, "validation_failed")
        self.assertIn("blank_title", result.error)
        self.assertEqual(publisher.sent, [])

    async def test_definite_failure_records_failed_state(self):
        failures = []

        def failure_recorder(item_id, channel_id, error, published_by=None):
            failures.append((item_id, channel_id, error, published_by))
            return PublicationResult(item_id, "telegram_failed", error=error)

        engine = RadarPublicationEngine(
            publisher=FakePublisher(error=DefiniteTelegramFailure("bad request")),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=failure_recorder,
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()), published_by=88)
        self.assertEqual(result.status, "telegram_failed")
        self.assertEqual(failures, [("radar-1", "@vitrinspain", "bad request", 88)])

    async def test_ambiguous_failure_does_not_record_failed_state(self):
        engine = RadarPublicationEngine(
            publisher=FakePublisher(error=AmbiguousTelegramFailure("timeout")),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("ambiguous failure must not mark failed"),
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertEqual(result.status, "telegram_ambiguous")

    async def test_persistence_failure_requires_reconciliation(self):
        response = TelegramPublicationResponse("@vitrinspain", 999, "https://t.me/vitrinspain/999")
        engine = RadarPublicationEngine(
            publisher=FakePublisher(response=response),
            success_recorder=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run after send"),
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(result.telegram_message_id, 999)
        self.assertEqual(result.channel_post_url, "https://t.me/vitrinspain/999")

    async def test_run_reports_each_outcome_without_stopping_batch(self):
        items = [
            EligiblePublicationItem(ready_item(id="good")),
            EligiblePublicationItem(ready_item(id="invalid", title="")),
        ]

        async def publish_side_effect(item, dry_run=False, published_by=None):
            if item.id == "good":
                return PublicationResult(item.id, "published")
            return PublicationResult(item.id, "validation_failed", error="blank_title")

        engine = RadarPublicationEngine(
            loader=lambda **kwargs: items,
            publisher=FakePublisher(),
            success_recorder=lambda *args, **kwargs: None,
            failure_recorder=lambda *args, **kwargs: None,
            existing_success_loader=lambda item_id: None,
            existing_message_loader=lambda item_id: None,
        )
        engine.publish_item = publish_side_effect
        report = await engine.run(limit=999, include_failed=True)
        self.assertEqual(report.loaded, 2)
        self.assertEqual(report.processed, 2)
        self.assertEqual(report.published, 1)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.failed, 0)


if __name__ == "__main__":
    unittest.main()
