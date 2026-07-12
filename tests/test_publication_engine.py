import unittest

from radar_engine.publication.engine import RadarPublicationEngine
from radar_engine.publication.models import (
    EligiblePublicationItem,
    PublicationAttempt,
    PublicationClaim,
    PublicationResult,
    TelegramPublicationResponse,
)
from radar_engine.publication.publisher import AmbiguousTelegramFailure, DefiniteTelegramFailure, PublicationValidationError
from tests.test_publication_publisher import ready_item


class FakePublisher:
    channel_id = "@vitrinspain"

    def __init__(self, response=None, error=None):
        self.response = response or TelegramPublicationResponse("@vitrinspain", 123)
        self.error = error
        self.sent = []

    async def publish(self, item):
        if isinstance(self.error, PublicationValidationError):
            raise self.error
        self.sent.append(item.id)
        if self.error:
            raise self.error
        return self.response


def fake_attempt(status="claimed", attempt_status="sending", message_id=None):
    attempt = PublicationAttempt(
        radar_item_id="radar-1",
        attempt_token="attempt-1",
        attempt_status=attempt_status,
        telegram_message_id=message_id,
        channel_id="@vitrinspain" if message_id else None,
        channel_post_url=f"https://t.me/vitrinspain/{message_id}" if message_id else None,
    )
    return PublicationClaim(status, attempt)


def publication_engine(**overrides):
    defaults = {
        "success_recorder": lambda item_id, response, published_by=None: PublicationResult(
            item_id,
            "published",
            telegram_message_id=response.telegram_message_id,
            channel_id=response.channel_id,
            channel_post_url=response.channel_post_url,
        ),
        "failure_recorder": lambda item_id, channel_id, error, published_by=None: PublicationResult(
            item_id,
            "telegram_failed",
            channel_id=channel_id,
            error=error,
        ),
        "existing_success_loader": lambda item_id: None,
        "existing_message_loader": lambda item_id: None,
        "attempt_claimer": lambda item_id, claimed_by=None: fake_attempt(),
        "attempt_sent_marker": lambda attempt, response: PublicationAttempt(
            radar_item_id=attempt.radar_item_id,
            attempt_token=attempt.attempt_token,
            attempt_status="sent_unpersisted",
            telegram_message_id=response.telegram_message_id,
            channel_id=response.channel_id,
            channel_post_url=response.channel_post_url,
        ),
        "attempt_completed_marker": lambda attempt: None,
        "attempt_failed_marker": lambda attempt, error: None,
        "attempt_ambiguous_marker": lambda attempt, error: None,
        "attempt_cancelled_marker": lambda attempt, error: None,
    }
    defaults.update(overrides)
    return RadarPublicationEngine(**defaults)


class PublicationEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_publication_records_success_and_completes_attempt(self):
        item = EligiblePublicationItem(ready_item(id="radar-1"))
        successes = []
        completed = []

        def success_recorder(item_id, response, published_by=None):
            successes.append((item_id, response.telegram_message_id, published_by))
            return PublicationResult(item_id, "published", telegram_message_id=response.telegram_message_id)

        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            success_recorder=success_recorder,
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            attempt_completed_marker=lambda attempt: completed.append(attempt.attempt_status),
        )
        result = await engine.publish_item(item, published_by=77)
        self.assertTrue(result.published)
        self.assertEqual(publisher.sent, ["radar-1"])
        self.assertEqual(successes, [("radar-1", 123, 77)])
        self.assertEqual(completed, ["sent_unpersisted"])

    async def test_duplicate_publication_is_blocked_before_claim_or_send(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_success_loader=lambda item_id: {"telegram_message_id": 55},
            attempt_claimer=lambda *args, **kwargs: self.fail("claim should not run"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.already_published)
        self.assertEqual(result.telegram_message_id, 55)
        self.assertEqual(publisher.sent, [])

    async def test_existing_channel_message_is_blocked_before_claim_or_send(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            existing_message_loader=lambda item_id: {"channel_message_id": 56},
            attempt_claimer=lambda *args, **kwargs: self.fail("claim should not run"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.already_published)
        self.assertEqual(result.telegram_message_id, 56)
        self.assertEqual(publisher.sent, [])

    async def test_dry_run_validates_without_claiming_sending_or_persisting(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            attempt_claimer=lambda *args, **kwargs: self.fail("dry run should not claim"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()), dry_run=True)
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(publisher.sent, [])

    async def test_validation_failure_skips_claim_and_send(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            attempt_claimer=lambda *args, **kwargs: self.fail("invalid item should not claim"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item(title="")))
        self.assertEqual(result.status, "validation_failed")
        self.assertIn("blank_title", result.error)
        self.assertEqual(publisher.sent, [])

    async def test_publisher_validation_failure_closes_acquired_claim_without_send(self):
        publisher = FakePublisher(error=PublicationValidationError("rendered post is empty"))
        cancelled = []
        engine = publication_engine(
            publisher=publisher,
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
            attempt_cancelled_marker=lambda attempt, error: cancelled.append((attempt.attempt_token, error)),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertEqual(result.status, "validation_failed")
        self.assertEqual(cancelled, [("attempt-1", "rendered post is empty")])
        self.assertEqual(publisher.sent, [])

    async def test_active_claim_prevents_send(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            attempt_claimer=lambda item_id, claimed_by=None: fake_attempt("publication_in_progress"),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertEqual(result.status, "publication_in_progress")
        self.assertEqual(publisher.sent, [])

    async def test_reconcilable_attempt_prevents_new_send(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            attempt_claimer=lambda item_id, claimed_by=None: fake_attempt(
                "reconciliation_required",
                attempt_status="sent_unpersisted",
                message_id=555,
            ),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(result.telegram_message_id, 555)
        self.assertEqual(publisher.sent, [])

    async def test_retry_after_expired_sending_claim_does_not_call_telegram(self):
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            attempt_claimer=lambda item_id, claimed_by=None: fake_attempt(
                "reconciliation_required",
                attempt_status="ambiguous",
            ),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run"),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(publisher.sent, [])

    async def test_simulated_concurrent_calls_send_once(self):
        claims = [fake_attempt("claimed"), fake_attempt("publication_in_progress")]
        publisher = FakePublisher()
        engine = publication_engine(
            publisher=publisher,
            attempt_claimer=lambda item_id, claimed_by=None: claims.pop(0),
        )
        first = await engine.publish_item(EligiblePublicationItem(ready_item()))
        second = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(first.published)
        self.assertEqual(second.status, "publication_in_progress")
        self.assertEqual(publisher.sent, ["radar-1"])

    async def test_definite_failure_closes_attempt_and_records_failed_state(self):
        failures = []
        failed_attempts = []

        def failure_recorder(item_id, channel_id, error, published_by=None):
            failures.append((item_id, channel_id, error, published_by))
            return PublicationResult(item_id, "telegram_failed", error=error)

        engine = publication_engine(
            publisher=FakePublisher(error=DefiniteTelegramFailure("bad request")),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=failure_recorder,
            attempt_failed_marker=lambda attempt, error: failed_attempts.append((attempt.attempt_token, error)),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()), published_by=88)
        self.assertEqual(result.status, "telegram_failed")
        self.assertEqual(failures, [("radar-1", "@vitrinspain", "bad request", 88)])
        self.assertEqual(failed_attempts, [("attempt-1", "bad request")])

    async def test_ambiguous_failure_marks_attempt_without_generic_failure(self):
        ambiguous_attempts = []
        engine = publication_engine(
            publisher=FakePublisher(error=AmbiguousTelegramFailure("timeout")),
            success_recorder=lambda *args, **kwargs: self.fail("success recorder should not run"),
            failure_recorder=lambda *args, **kwargs: self.fail("ambiguous failure must not mark failed"),
            attempt_ambiguous_marker=lambda attempt, error: ambiguous_attempts.append((attempt.attempt_token, error)),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertEqual(result.status, "telegram_ambiguous")
        self.assertEqual(ambiguous_attempts, [("attempt-1", "timeout")])

    async def test_successful_send_stores_identifiers_before_final_persistence(self):
        order = []
        response = TelegramPublicationResponse("@vitrinspain", 999, "https://t.me/vitrinspain/999")

        def mark_sent(attempt, response):
            order.append(("sent", response.telegram_message_id))
            return PublicationAttempt(
                radar_item_id=attempt.radar_item_id,
                attempt_token=attempt.attempt_token,
                attempt_status="sent_unpersisted",
                telegram_message_id=response.telegram_message_id,
                channel_id=response.channel_id,
                channel_post_url=response.channel_post_url,
            )

        def success(item_id, response, published_by=None):
            order.append(("success", response.telegram_message_id))
            return PublicationResult(item_id, "published", telegram_message_id=response.telegram_message_id)

        engine = publication_engine(
            publisher=FakePublisher(response=response),
            attempt_sent_marker=mark_sent,
            success_recorder=success,
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.published)
        self.assertEqual(order, [("sent", 999), ("success", 999)])

    async def test_persistence_failure_leaves_reconcilable_attempt(self):
        response = TelegramPublicationResponse("@vitrinspain", 999, "https://t.me/vitrinspain/999")
        sent_attempts = []
        engine = publication_engine(
            publisher=FakePublisher(response=response),
            success_recorder=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db down")),
            failure_recorder=lambda *args, **kwargs: self.fail("failure recorder should not run after send"),
            attempt_sent_marker=lambda attempt, response: sent_attempts.append(
                (attempt.attempt_token, response.telegram_message_id)
            )
            or PublicationAttempt(
                radar_item_id=attempt.radar_item_id,
                attempt_token=attempt.attempt_token,
                attempt_status="sent_unpersisted",
                telegram_message_id=response.telegram_message_id,
                channel_id=response.channel_id,
                channel_post_url=response.channel_post_url,
            ),
        )
        result = await engine.publish_item(EligiblePublicationItem(ready_item()))
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(result.telegram_message_id, 999)
        self.assertEqual(result.channel_post_url, "https://t.me/vitrinspain/999")
        self.assertEqual(sent_attempts, [("attempt-1", 999)])

    async def test_run_reports_each_outcome_without_stopping_batch(self):
        items = [
            EligiblePublicationItem(ready_item(id="good")),
            EligiblePublicationItem(ready_item(id="invalid", title="")),
        ]

        async def publish_side_effect(item, dry_run=False, published_by=None):
            if item.id == "good":
                return PublicationResult(item.id, "published")
            return PublicationResult(item.id, "validation_failed", error="blank_title")

        engine = publication_engine(
            loader=lambda **kwargs: items,
            publisher=FakePublisher(),
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
