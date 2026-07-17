import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.publication.engine import RadarPublicationEngine
from radar_engine.publication.models import EligiblePublicationItem, PublicationResult
from radar_engine.review.models import RadarReviewQueueItem, RadarSummaryForReview
from radar_engine.scheduler import RadarBOEIngestionScheduler
from radar_engine.urgent import (
    UrgentAutoPublicationEngine,
    UrgentAutoPublishConfig,
    evaluate_urgent_candidate,
    urgent_admin_notification_text,
)


NOW = datetime(2026, 7, 17, 12, 0, 0)


def make_item(category="alert", **overrides):
    metadata = overrides.pop("metadata", {"actionability_gate": {"passed": True}, "actionability_score": 95})
    candidate = RadarCandidate(
        raw_item_id="raw-1",
        source_key="aemet",
        source_name=overrides.pop("source_name", "AEMET"),
        external_id="alert-1",
        title=overrides.pop("title", "هشدار قرمز گرما"),
        body=overrides.pop("body", "خطر فعال است و شهروندان باید در خانه بمانند."),
        language="es",
        source_url=overrides.pop("source_url", "https://www.aemet.es/alert/1"),
        canonical_url=None,
        published_at=overrides.pop("published_at", NOW - timedelta(hours=1)),
        valid_from=overrides.pop("valid_from", NOW - timedelta(hours=1)),
        valid_until=overrides.pop("valid_until", NOW + timedelta(hours=5)),
        source_category="Weather",
        source_location="Spain",
        source_type=overrides.pop("source_type", "official"),
        trust_level=overrides.pop("trust_level", 5),
        country="Spain",
        candidate_status=overrides.pop("candidate_status", "pending_ai"),
        metadata=metadata,
    )
    summary = RadarSummaryForReview(
        ai_result_id="ai-1",
        headline="هشدار قرمز گرما",
        summary="هشدار رسمی و فعال برای گرمای شدید صادر شده است.",
        why_it_matters="خطر فوری برای سلامت",
        confidence=0.98,
    )
    classification = RadarClassificationResult(
        candidate_id="candidate-1",
        primary_category=category,
        category_tags=[category],
        audience_tags=["all"],
        cities=[],
        geographic_scope="national",
        urgency=overrides.pop("urgency", "urgent"),
        priority_score=95,
        confidence=overrides.pop("confidence", 0.95),
        model_name="gemini",
        prompt_version="v1",
        processing_time_ms=10,
    )
    return RadarReviewQueueItem("candidate-1", candidate, summary, classification)


CONFIG = UrgentAutoPublishConfig(True, 90, 0.90, 30, 10)


class UrgentEligibilityTests(unittest.TestCase):
    def test_ordinary_categories_never_auto_publish(self):
        for category in ("legal", "job", "discount", "event", "weather"):
            with self.subTest(category=category):
                decision = evaluate_urgent_candidate(make_item(category), CONFIG, now=NOW)
                self.assertFalse(decision.eligible)
                self.assertIn("not_alert", decision.reasons)

    def test_urgent_publishing_disabled(self):
        decision = evaluate_urgent_candidate(make_item(), UrgentAutoPublishConfig(), now=NOW)
        self.assertFalse(decision.eligible)
        self.assertIn("disabled", decision.reasons)

    def test_eligible_urgent_alert(self):
        self.assertTrue(evaluate_urgent_candidate(make_item(), CONFIG, now=NOW).eligible)

    def test_score_and_confidence_thresholds(self):
        low_score = make_item(metadata={"actionability_gate": {"passed": True}, "actionability_score": 89})
        low_confidence = make_item(confidence=0.89)
        self.assertIn("low_actionability_score", evaluate_urgent_candidate(low_score, CONFIG, now=NOW).reasons)
        self.assertIn("low_confidence", evaluate_urgent_candidate(low_confidence, CONFIG, now=NOW).reasons)

    def test_untrusted_source_and_invalid_url(self):
        self.assertIn("untrusted_source", evaluate_urgent_candidate(make_item(), CONFIG, now=NOW, trusted_source=False).reasons)
        self.assertIn("invalid_source_url", evaluate_urgent_candidate(make_item(source_url="ftp://bad"), CONFIG, now=NOW).reasons)

    def test_expired_duplicate_rejected_and_already_evaluated(self):
        expired = make_item(valid_until=NOW - timedelta(minutes=1))
        duplicate = make_item(metadata={"actionability_gate": {"passed": True}, "actionability_score": 95, "duplicate": True})
        rejected = make_item(candidate_status="rejected")
        published = make_item(metadata={"actionability_gate": {"passed": True}, "actionability_score": 95, "urgent_auto_publish": {"status": "published"}})
        self.assertIn("not_current", evaluate_urgent_candidate(expired, CONFIG, now=NOW).reasons)
        self.assertIn("duplicate", evaluate_urgent_candidate(duplicate, CONFIG, now=NOW).reasons)
        self.assertIn("rejected", evaluate_urgent_candidate(rejected, CONFIG, now=NOW).reasons)
        self.assertIn("already_evaluated", evaluate_urgent_candidate(published, CONFIG, now=NOW).reasons)

    def test_gate_highest_urgency_cooldown_and_daily_limit(self):
        failed_gate = make_item(metadata={"actionability_gate": {"passed": False}, "actionability_score": 95})
        self.assertIn("actionability_gate_failed", evaluate_urgent_candidate(failed_gate, CONFIG, now=NOW).reasons)
        self.assertIn("not_highest_urgency", evaluate_urgent_candidate(make_item(urgency="high"), CONFIG, now=NOW).reasons)
        self.assertIn("cooldown", evaluate_urgent_candidate(make_item(), CONFIG, now=NOW, cooldown_active=True).reasons)
        self.assertIn("daily_safety_limit", evaluate_urgent_candidate(make_item(), CONFIG, now=NOW, daily_limit_reached=True).reasons)

    def test_configuration_clamps_and_true_values(self):
        from unittest.mock import patch

        env = {
            "RADAR_URGENT_AUTO_PUBLISH_ENABLED": "yes",
            "RADAR_URGENT_AUTO_PUBLISH_MIN_SCORE": "999",
            "RADAR_URGENT_AUTO_PUBLISH_MIN_CONFIDENCE": "-1",
            "RADAR_URGENT_AUTO_PUBLISH_COOLDOWN_MINUTES": "1",
        }
        with patch.dict("os.environ", env, clear=False):
            config = UrgentAutoPublishConfig.from_env()
        self.assertTrue(config.enabled)
        self.assertEqual(config.min_score, 100)
        self.assertEqual(config.min_confidence, 0.0)
        self.assertEqual(config.cooldown_minutes, 5)


class UrgentEngineTests(unittest.IsolatedAsyncioTestCase):
    def engine(self, items, result, **overrides):
        publisher = Mock()
        publisher.publish_item = AsyncMock(return_value=result)
        outcomes = []
        engine = UrgentAutoPublicationEngine(
            config=CONFIG,
            loader=lambda limit: items,
            trusted_source_checker=lambda candidate: True,
            safety_state_loader=lambda: {"last_published_at": None, "published_today": 0},
            item_preparer=lambda item, decision: {
                "id": f"radar-{item.candidate_id}", "title": item.candidate.title,
                "summary": item.summary.summary, "content_status": "ready", "channel_status": "not_sent",
                "is_published": False, "source_name": item.candidate.source_name, "source_url": item.candidate.source_url,
            },
            publisher=publisher,
            outcome_recorder=lambda *args: outcomes.append(args),
            admin_notifier=overrides.get("admin_notifier"),
            now_func=lambda: NOW,
        )
        return engine, publisher, outcomes

    async def test_telegram_success_records_and_notifies_admin(self):
        notifier = AsyncMock(return_value=2)
        result = PublicationResult("radar-candidate-1", "published", telegram_message_id=42)
        engine, publisher, outcomes = self.engine([make_item()], result, admin_notifier=notifier)
        report = await engine.run()
        self.assertEqual(report.published, 1)
        self.assertEqual(report.notified_admins, 2)
        publisher.publish_item.assert_awaited_once()
        self.assertEqual(len(outcomes), 1)
        notifier.assert_awaited_once()

    async def test_telegram_failure_falls_back_to_review(self):
        result = PublicationResult("radar-candidate-1", "telegram_failed", error="network")
        engine, _, outcomes = self.engine([make_item()], result)
        report = await engine.run()
        self.assertEqual(report.failed, 1)
        self.assertEqual(report.fallback_review, 1)
        self.assertEqual(len(outcomes), 1)

    async def test_only_one_urgent_alert_is_published_per_cycle(self):
        first = make_item()
        second = make_item()
        second.candidate_id = "candidate-2"
        result = PublicationResult("radar-candidate-1", "published", telegram_message_id=42)
        engine, publisher, _ = self.engine([first, second], result)
        report = await engine.run()
        self.assertEqual(report.published, 1)
        publisher.publish_item.assert_awaited_once()

    async def test_noneligible_urgent_stays_in_review_without_publication(self):
        result = PublicationResult("unused", "published")
        engine, publisher, outcomes = self.engine([make_item(confidence=0.2)], result)
        report = await engine.run()
        self.assertEqual(report.fallback_review, 1)
        publisher.publish_item.assert_not_awaited()
        self.assertEqual(outcomes, [])

    def test_admin_notification_contains_required_audit_values(self):
        item = make_item()
        decision = evaluate_urgent_candidate(item, CONFIG, now=NOW)
        text = urgent_admin_notification_text(item, decision)
        for expected in ("🚨 هشدار فوری", item.candidate.title, "AEMET", "95", "0.95"):
            self.assertIn(expected, text)

    async def test_manual_publication_engine_has_no_daily_limit(self):
        items = [
            EligiblePublicationItem({"id": "one"}),
            EligiblePublicationItem({"id": "two"}),
        ]
        engine = RadarPublicationEngine(
            loader=lambda **kwargs: items,
            publisher=Mock(), success_recorder=Mock(), failure_recorder=Mock(),
            existing_success_loader=Mock(), existing_message_loader=Mock(), attempt_claimer=Mock(),
            attempt_sent_marker=Mock(), attempt_completed_marker=Mock(), attempt_failed_marker=Mock(),
            attempt_ambiguous_marker=Mock(), attempt_cancelled_marker=Mock(),
        )
        engine.publish_item = AsyncMock(side_effect=[PublicationResult("one", "published"), PublicationResult("two", "published")])
        report = await engine.run(limit=20)
        self.assertEqual(report.published, 2)
        self.assertEqual(engine.publish_item.await_count, 2)

    async def test_scheduler_runs_urgent_stage_after_classification(self):
        events = []

        async def stage(name, value=None):
            events.append(name)
            return value

        class Lock:
            def __enter__(self):
                return True

            def __exit__(self, *args):
                return None

        scheduler = RadarBOEIngestionScheduler(
            ingest_stage=lambda: stage("ingest"),
            pipeline_stage=lambda: stage("pipeline"),
            actionability_backfill_stage=lambda: stage("backfill"),
            ai_stage=lambda: stage("ai"),
            classification_stage=lambda: stage("classification"),
            urgent_publication_stage=lambda: stage("urgent"),
            review_notification_stage=lambda count: stage("review"),
            lock_factory=Lock,
        )
        await scheduler.run_once()
        self.assertEqual(events, ["ingest", "pipeline", "backfill", "ai", "classification", "urgent", "review"])


if __name__ == "__main__":
    unittest.main()
