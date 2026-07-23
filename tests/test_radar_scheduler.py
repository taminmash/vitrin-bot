import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from radar_engine.ai.engine import AIReport
from radar_engine.classification.engine import ClassificationReport
from radar_engine.pipeline.engine import PipelineReport
from radar_engine.scheduler import (
    ADVISORY_LOCK_NAME,
    DEFAULT_FETCH_INTERVAL_MINUTES,
    PostgresAdvisoryLock,
    RadarBOEIngestionScheduler,
    RadarReviewNotifier,
    advisory_lock_key,
    _default_ingest_stage,
    ai_batch_limit_from_env,
    ai_request_delay_seconds_from_env,
    auto_ingestion_enabled,
    fetch_interval_minutes_from_env,
    radar_review_notification_text,
    start_radar_scheduler,
    stop_radar_scheduler,
)
from radar_engine.source_manager import IngestionReport


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def immediate_report(report):
    return report


class FakeApplication:
    def __init__(self):
        self.bot_data = {}
        self.bot = FakeBot()


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, *, chat_id, text):
        self.messages.append({"chat_id": chat_id, "text": text})


class FakeLock:
    def __init__(self, acquired=True, events=None):
        self.acquired = acquired
        self.events = events if events is not None else []

    def __enter__(self):
        self.events.append("enter")
        return self.acquired

    def __exit__(self, exc_type, exc, tb):
        self.events.append("exit")


class RadarSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_ingestion_isolates_one_source_failure(self):
        class FakeManager:
            def __init__(self):
                self.calls = []

            def source_keys(self):
                return ("empleo_publico", "2k_madrid", "keyfactor_spain")

            async def ingest_source(self, source_key):
                self.calls.append(source_key)
                if source_key == "2k_madrid":
                    return IngestionReport(source_key, failed_count=1, errors=["temporary upstream failure"])
                return IngestionReport(source_key, fetched_count=1, inserted_count=1)

        manager = FakeManager()
        if hasattr(_default_ingest_stage, "_job_source_last_runs"):
            delattr(_default_ingest_stage, "_job_source_last_runs")
        with patch("radar_engine.scheduler.build_default_source_manager", return_value=manager), patch(
            "radar_engine.scheduler.source_interval_minutes", return_value=60
        ):
            report = await _default_ingest_stage("boe")()

        self.assertEqual(manager.calls, ["empleo_publico", "2k_madrid", "keyfactor_spain"])
        self.assertEqual(report.fetched_count, 2)
        self.assertEqual(report.inserted_count, 2)
        self.assertEqual(report.failed_count, 1)
        self.assertIn("2k_madrid: temporary upstream failure", report.errors)

    def test_interval_defaults_and_env_override(self):
        self.assertEqual(fetch_interval_minutes_from_env(""), DEFAULT_FETCH_INTERVAL_MINUTES)
        self.assertEqual(fetch_interval_minutes_from_env("15"), 15)
        self.assertEqual(fetch_interval_minutes_from_env("0"), 1)
        self.assertEqual(fetch_interval_minutes_from_env("bad"), DEFAULT_FETCH_INTERVAL_MINUTES)

    def test_enabled_switch_defaults_on_and_accepts_false_values(self):
        self.assertTrue(auto_ingestion_enabled(None))
        self.assertTrue(auto_ingestion_enabled(""))
        self.assertTrue(auto_ingestion_enabled("yes"))
        for value in ("0", "false", "no", "off", " FALSE "):
            self.assertFalse(auto_ingestion_enabled(value))

    def test_ai_batch_and_delay_env_are_bounded(self):
        self.assertEqual(ai_batch_limit_from_env(None, provider="gemini"), 1)
        self.assertEqual(ai_batch_limit_from_env(None, provider="openai"), 10)
        self.assertEqual(ai_batch_limit_from_env("0"), 1)
        self.assertEqual(ai_batch_limit_from_env("25"), 10)
        self.assertEqual(ai_batch_limit_from_env("999"), 10)
        self.assertEqual(ai_batch_limit_from_env("bad", provider="gemini"), 1)
        self.assertEqual(ai_request_delay_seconds_from_env(None, provider="gemini"), 15.0)
        self.assertEqual(ai_request_delay_seconds_from_env(None, provider="openai"), 1.0)
        self.assertEqual(ai_request_delay_seconds_from_env("-1"), 0.0)
        self.assertEqual(ai_request_delay_seconds_from_env("2.5"), 2.5)
        self.assertEqual(ai_request_delay_seconds_from_env("99"), 60.0)
        self.assertEqual(ai_request_delay_seconds_from_env("bad", provider="gemini"), 15.0)

    def test_advisory_lock_uses_stable_dedicated_key(self):
        self.assertEqual(advisory_lock_key(), advisory_lock_key(ADVISORY_LOCK_NAME))
        self.assertEqual(advisory_lock_key(), advisory_lock_key())
        self.assertNotEqual(advisory_lock_key(), advisory_lock_key("other"))

    async def test_scheduler_running_property_reflects_active_task(self):
        scheduler = RadarBOEIngestionScheduler(sleep_func=asyncio.sleep)
        scheduler._task = asyncio.create_task(asyncio.sleep(60))
        try:
            self.assertTrue(scheduler.is_running)
            self.assertFalse(scheduler.is_stopped)
        finally:
            scheduler._task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await scheduler._task

    async def test_scheduler_stopped_property_reflects_done_task(self):
        scheduler = RadarBOEIngestionScheduler(sleep_func=asyncio.sleep)
        task = asyncio.create_task(asyncio.sleep(0))
        await task
        scheduler._task = task
        self.assertFalse(scheduler.is_running)
        self.assertTrue(scheduler.is_stopped)

    async def test_scheduler_stopped_property_reflects_stop_event(self):
        scheduler = RadarBOEIngestionScheduler(sleep_func=asyncio.sleep)
        scheduler._task = asyncio.create_task(asyncio.sleep(60))
        scheduler._stop_event.set()
        try:
            self.assertFalse(scheduler.is_running)
            self.assertTrue(scheduler.is_stopped)
        finally:
            scheduler._task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await scheduler._task

    async def test_scheduler_starts_and_stores_instance(self):
        class FakeScheduler:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs
                self.started = False
                self.stopped = False

            started = False
            stopped = False

            def start(self):
                self.started = True

            async def stop(self):
                self.stopped = True

        app = FakeApplication()
        with patch("radar_engine.scheduler.RadarBOEIngestionScheduler", FakeScheduler):
            await start_radar_scheduler(app)
        scheduler = app.bot_data["radar_boe_scheduler"]
        self.assertTrue(scheduler.started)
        await stop_radar_scheduler(app)
        self.assertTrue(scheduler.stopped)

    async def test_disabled_environment_prevents_scheduler_startup(self):
        app = FakeApplication()
        with patch.dict("os.environ", {"RADAR_AUTO_INGESTION_ENABLED": "off"}), self.assertLogs(
            "radar_engine.scheduler", level="INFO"
        ) as logs:
            await start_radar_scheduler(app)
        self.assertNotIn("radar_boe_scheduler", app.bot_data)
        self.assertIn("Radar automatic ingestion is disabled", "\n".join(logs.output))

    async def test_duplicate_start_does_not_create_second_scheduler(self):
        class FakeScheduler:
            created = 0

            def __init__(self, *args, **kwargs):
                type(self).created += 1
                self.started = False

            def start(self):
                self.started = True

        app = FakeApplication()
        with patch("radar_engine.scheduler.RadarBOEIngestionScheduler", FakeScheduler):
            await start_radar_scheduler(app)
            first = app.bot_data["radar_boe_scheduler"]
            await start_radar_scheduler(app)
        self.assertIs(app.bot_data["radar_boe_scheduler"], first)
        self.assertEqual(FakeScheduler.created, 1)

    def test_bot_startup_wires_scheduler_hooks(self):
        bot_text = (PROJECT_ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn("start_radar_scheduler", bot_text)
        self.assertIn("stop_radar_scheduler", bot_text)
        self.assertIn("async def post_init(application):", bot_text)
        self.assertIn("await set_public_bot_commands(application)", bot_text)
        self.assertIn("await start_radar_scheduler(application)", bot_text)
        self.assertIn(".post_init(post_init)", bot_text)
        self.assertIn(".post_shutdown(stop_radar_scheduler)", bot_text)

    async def test_pipeline_called_once_per_cycle_and_metrics_collected(self):
        calls = []

        async def ingest():
            return IngestionReport("boe", fetched_count=3, inserted_count=2, duplicate_count=1)

        async def pipeline():
            calls.append("pipeline")
            return PipelineReport(loaded_count=4, created_count=2, rejected_count=1)

        async def backfill():
            from radar_engine.pipeline.actionability_backfill import ActionabilityBackfillReport

            return ActionabilityBackfillReport(recovered=1)

        async def notify(_queued):
            return 2

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=ingest,
            pipeline_stage=pipeline,
            actionability_backfill_stage=backfill,
            ai_stage=lambda: immediate_report(AIReport(completed=2)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=2)),
            review_notification_stage=notify,
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertEqual(calls, ["pipeline"])
        self.assertEqual(report.fetched, 3)
        self.assertEqual(report.skipped_duplicate, 1)
        self.assertEqual(report.inserted_raw, 2)
        self.assertEqual(report.candidate_created, 2)
        self.assertEqual(report.raw_backlog_selected, 4)
        self.assertEqual(report.candidate_recovered, 1)
        self.assertEqual(report.candidate_rejected, 1)
        self.assertEqual(report.ai_completed, 2)
        self.assertEqual(report.classification_completed, 2)
        self.assertEqual(report.queued_for_review, 2)
        self.assertEqual(report.notification_sent, 2)

    async def test_scheduler_log_exposes_requested_pipeline_metrics(self):
        scheduler = RadarBOEIngestionScheduler(
            ingest_stage=lambda: immediate_report(IngestionReport("boe")),
            pipeline_stage=lambda: immediate_report(PipelineReport(loaded_count=3, created_count=2, rejected_count=1)),
            ai_stage=lambda: immediate_report(AIReport(processed=2, completed=2)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=2)),
            review_notification_stage=lambda _queued: immediate_report(1),
            lock_factory=lambda: FakeLock(True),
        )
        with self.assertLogs("radar_engine.scheduler", level="INFO") as logs:
            await scheduler.run_once()
        metrics = "\n".join(logs.output)
        for label in (
            "Raw backlog selected=3", "Candidate created=2", "Candidate recovered=0",
            "Candidate rejected=1", "AI processed=2", "AI completed=2",
            "Review queued=2", "Notification sent=1",
        ):
            self.assertIn(label, metrics)

    async def test_bounded_actionability_backfill_runs_before_ai(self):
        calls = []

        async def backfill():
            calls.append("backfill")
            from radar_engine.pipeline.actionability_backfill import ActionabilityBackfillReport

            return ActionabilityBackfillReport(evaluated=2, passed=1, rejected=1, remaining=3)

        async def ai():
            calls.append("ai")
            return AIReport(completed=0)

        scheduler = RadarBOEIngestionScheduler(
            ingest_stage=lambda: immediate_report(IngestionReport("boe")),
            pipeline_stage=lambda: immediate_report(PipelineReport()),
            actionability_backfill_stage=backfill,
            ai_stage=ai,
            classification_stage=lambda: immediate_report(ClassificationReport()),
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertEqual(calls, ["backfill", "ai"])
        self.assertEqual(report.actionability_backfill_evaluated, 2)
        self.assertEqual(report.actionability_backfill_passed, 1)
        self.assertEqual(report.actionability_backfill_rejected, 1)
        self.assertEqual(report.actionability_backfill_remaining, 3)

    async def test_scheduler_notifies_review_stage_after_classification(self):
        calls = []

        async def notify(new_items_hint):
            calls.append(new_items_hint)

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=3)),
            review_notification_stage=notify,
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertEqual(report.queued_for_review, 3)
        self.assertEqual(calls, [3])

    async def test_ai_stopped_early_cycle_evaluates_review_notification_timer_once(self):
        now = {"value": 0}
        sent = []

        async def send_message(*, chat_id, text):
            sent.append((chat_id, text))

        pending_totals = iter([1, 1])
        notifier = RadarReviewNotifier(
            admin_ids=[101],
            send_message=send_message,
            pending_review_count=lambda: next(pending_totals),
            time_func=lambda: now["value"],
        )
        classification_calls = []

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=1)),
            review_notification_stage=notifier.notify_if_pending_increased,
            lock_factory=lambda: FakeLock(True),
        )
        first = await scheduler.run_once()
        self.assertEqual(first.queued_for_review, 1)
        self.assertEqual(sent, [])

        now["value"] = 30 * 60
        scheduler.ai_stage = lambda: immediate_report(AIReport(remaining=1, stopped_early=True))

        async def classification_should_not_run():
            classification_calls.append("classification")
            return ClassificationReport(completed=0)

        scheduler.classification_stage = classification_should_not_run
        second = await scheduler.run_once()
        self.assertEqual(second.classification_completed, 0)
        self.assertEqual(classification_calls, [])
        self.assertEqual([chat_id for chat_id, _ in sent], [101])
        self.assertIn("1 new items are ready for review.", sent[0][1])

    async def test_duplicate_only_cycle_can_trigger_elapsed_review_notification(self):
        now = {"value": 0}
        sent = []

        async def send_message(*, chat_id, text):
            sent.append((chat_id, text))

        pending_totals = iter([1, 1])
        notifier = RadarReviewNotifier(
            admin_ids=[101],
            send_message=send_message,
            pending_review_count=lambda: next(pending_totals),
            time_func=lambda: now["value"],
        )
        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=1)),
            review_notification_stage=notifier.notify_if_pending_increased,
            lock_factory=lambda: FakeLock(True),
        )
        await scheduler.run_once()
        self.assertEqual(sent, [])

        now["value"] = 30 * 60
        scheduler.ingest_stage = lambda: immediate_report(IngestionReport("boe", fetched_count=1, duplicate_count=1))
        scheduler.pipeline_stage = lambda: immediate_report(PipelineReport(created_count=0))
        scheduler.ai_stage = lambda: immediate_report(AIReport(completed=0))
        scheduler.classification_stage = lambda: immediate_report(ClassificationReport(completed=0))
        second = await scheduler.run_once()
        self.assertEqual(second.queued_for_review, 0)
        self.assertEqual([chat_id for chat_id, _ in sent], [101])
        self.assertIn("Pending review: 1", sent[0][1])

    async def test_review_notification_evaluates_once_per_completed_cycle(self):
        calls = []

        async def notify(new_items_hint):
            calls.append(new_items_hint)

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=3)),
            review_notification_stage=notify,
            lock_factory=lambda: FakeLock(True),
        )
        await scheduler.run_once()
        self.assertEqual(calls, [3])

        calls.clear()
        scheduler.ai_stage = lambda: immediate_report(AIReport(remaining=1, stopped_early=True))
        await scheduler.run_once()
        self.assertEqual(calls, [0])

        calls.clear()
        scheduler.ai_stage = lambda: immediate_report(AIReport(completed=0))
        scheduler.classification_stage = lambda: immediate_report(ClassificationReport(completed=0))
        await scheduler.run_once()
        self.assertEqual(calls, [0])

    async def test_review_notification_error_does_not_fail_cycle(self):
        async def broken_notify(_new_items_hint):
            raise RuntimeError("telegram unavailable")

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=1)),
            review_notification_stage=broken_notify,
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertFalse(report.failed)
        self.assertIn("telegram unavailable", report.errors)

    async def test_db_lock_acquired_runs_cycle_and_releases_after_success(self):
        events = []
        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=1)),
            lock_factory=lambda: FakeLock(True, events),
        )
        report = await scheduler.run_once()
        self.assertFalse(report.skipped)
        self.assertEqual(report.inserted_raw, 1)
        self.assertEqual(events, ["enter", "exit"])

    async def test_db_lock_unavailable_skips_without_downstream_stages(self):
        calls = []
        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: calls.append("ingest") or immediate_report(IngestionReport("boe")),
            pipeline_stage=lambda: calls.append("pipeline") or immediate_report(PipelineReport()),
            ai_stage=lambda: calls.append("ai") or immediate_report(AIReport()),
            classification_stage=lambda: calls.append("classification") or immediate_report(ClassificationReport()),
            lock_factory=lambda: FakeLock(False),
        )
        with self.assertLogs("radar_engine.scheduler", level="INFO") as logs:
            report = await scheduler.run_once()
        self.assertTrue(report.skipped)
        self.assertEqual(calls, [])
        self.assertIn("Previous Radar BOE cycle is running in another process.", "\n".join(logs.output))

    async def test_advisory_lock_released_after_exception(self):
        events = []

        async def broken_ingest():
            raise RuntimeError("boom")

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=broken_ingest,
            pipeline_stage=lambda: immediate_report(PipelineReport()),
            ai_stage=lambda: immediate_report(AIReport()),
            classification_stage=lambda: immediate_report(ClassificationReport()),
            lock_factory=lambda: FakeLock(True, events),
        )
        report = await scheduler.run_once()
        self.assertTrue(report.failed)
        self.assertEqual(events, ["enter", "exit"])

    async def test_no_concurrent_execution(self):
        release = asyncio.Event()
        started = asyncio.Event()

        async def slow_ingest():
            started.set()
            await release.wait()
            return IngestionReport("boe", fetched_count=1)

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=slow_ingest,
            pipeline_stage=lambda: immediate_report(PipelineReport()),
            ai_stage=lambda: immediate_report(AIReport()),
            classification_stage=lambda: immediate_report(ClassificationReport()),
            lock_factory=lambda: FakeLock(True),
        )

        first = asyncio.create_task(scheduler.run_once())
        await started.wait()
        with self.assertLogs("radar_engine.scheduler", level="INFO") as logs:
            second = await scheduler.run_once()
        self.assertTrue(second.skipped)
        self.assertIn("Previous fetch cycle still running.", "\n".join(logs.output))
        release.set()
        await first

    async def test_start_logs_scheduler_started(self):
        async def sleep_forever(_seconds):
            await asyncio.Event().wait()

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe")),
            pipeline_stage=lambda: immediate_report(PipelineReport()),
            ai_stage=lambda: immediate_report(AIReport()),
            classification_stage=lambda: immediate_report(ClassificationReport()),
            lock_factory=lambda: FakeLock(True),
            sleep_func=sleep_forever,
        )
        with self.assertLogs("radar_engine.scheduler", level="INFO") as logs:
            scheduler.start()
        await scheduler.stop()
        self.assertIn("Radar scheduler started", "\n".join(logs.output))

    async def test_failure_recovery_and_retry_next_cycle(self):
        attempts = 0

        async def flaky_ingest():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("BOE unavailable")
            return IngestionReport("boe", fetched_count=1, inserted_count=1)

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=flaky_ingest,
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=1)),
            ai_stage=lambda: immediate_report(AIReport(completed=1)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=1)),
            lock_factory=lambda: FakeLock(True),
        )
        first = await scheduler.run_once()
        second = await scheduler.run_once()
        self.assertTrue(first.failed)
        self.assertIn("BOE unavailable", first.errors[0])
        self.assertFalse(second.failed)
        self.assertEqual(second.inserted_raw, 1)
        self.assertEqual(second.queued_for_review, 1)
        self.assertEqual(attempts, 2)

    async def test_total_boe_failure_does_not_call_downstream_ai_stages(self):
        calls = []
        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=0, failed_count=1)),
            pipeline_stage=lambda: calls.append("pipeline") or immediate_report(PipelineReport()),
            ai_stage=lambda: calls.append("ai") or immediate_report(AIReport()),
            classification_stage=lambda: calls.append("classification") or immediate_report(ClassificationReport()),
            review_notification_stage=lambda _new_items_hint: calls.append("notify") or immediate_report(None),
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertTrue(report.failed)
        self.assertEqual(calls, [])

    async def test_fatal_ingestion_retries_existing_pending_delivery_only(self):
        attempts = []
        failures = {202}

        async def send_message(*, chat_id, text):
            attempts.append((chat_id, text))
            if chat_id in failures:
                failures.remove(chat_id)
                raise RuntimeError("temporary telegram failure")

        pending_totals = iter([3, 3])
        notifier = RadarReviewNotifier(
            admin_ids=[101, 202],
            send_message=send_message,
            pending_review_count=lambda: next(pending_totals),
        )
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 1)
        self.assertEqual([chat_id for chat_id, _ in attempts], [101, 202])

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=0, failed_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport()),
            ai_stage=lambda: immediate_report(AIReport()),
            classification_stage=lambda: immediate_report(ClassificationReport()),
            review_notification_stage=notifier.notify_if_pending_increased,
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertTrue(report.failed)
        self.assertEqual([chat_id for chat_id, _ in attempts], [101, 202, 202])
        self.assertEqual(notifier.acknowledged_pending_review_count, 3)

    async def test_review_metric_is_newly_classification_completed_not_historical_total(self):
        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=0, duplicate_count=1)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=0)),
            ai_stage=lambda: immediate_report(AIReport(completed=0)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=1)),
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertEqual(report.queued_for_review, 1)

    async def test_ai_rate_limit_skips_classification_until_next_cycle(self):
        calls = []
        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=lambda: immediate_report(IngestionReport("boe", fetched_count=1, inserted_count=0)),
            pipeline_stage=lambda: immediate_report(PipelineReport(created_count=0)),
            ai_stage=lambda: immediate_report(
                AIReport(loaded=2, processed=1, completed=0, remaining=2, rate_limited=1, stopped_early=True)
            ),
            classification_stage=lambda: calls.append("classification") or immediate_report(ClassificationReport(completed=1)),
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertEqual(calls, [])
        self.assertEqual(report.ai_processed, 1)
        self.assertEqual(report.ai_completed, 0)
        self.assertEqual(report.ai_postponed, 2)
        self.assertEqual(report.classification_completed, 0)

    async def test_run_forever_retries_after_failed_cycle(self):
        attempts = 0
        scheduler = None

        async def flaky_ingest():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary")
            return IngestionReport("boe", fetched_count=1)

        async def sleep_once(_seconds):
            if attempts >= 2:
                scheduler._stop_event.set()
            await asyncio.sleep(0)

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=flaky_ingest,
            pipeline_stage=lambda: immediate_report(PipelineReport()),
            ai_stage=lambda: immediate_report(AIReport()),
            classification_stage=lambda: immediate_report(ClassificationReport()),
            lock_factory=lambda: FakeLock(True),
            sleep_func=sleep_once,
        )
        await scheduler.run_forever()
        self.assertEqual(attempts, 2)


class PostgresAdvisoryLockTests(unittest.TestCase):
    def test_postgres_lock_acquire_and_release_sql(self):
        class Cursor:
            def __init__(self):
                self.sql = []

            def execute(self, sql, params):
                self.sql.append((sql, params))

            def fetchone(self):
                return (True,)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

        class Connection:
            def __init__(self):
                self.autocommit = False
                self.cursor_obj = Cursor()
                self.closed = False

            def cursor(self):
                return self.cursor_obj

            def close(self):
                self.closed = True

        conn = Connection()
        with PostgresAdvisoryLock(connection_factory=lambda: conn) as acquired:
            self.assertTrue(acquired)
            self.assertTrue(conn.autocommit)
        sql_text = "\n".join(sql for sql, _ in conn.cursor_obj.sql)
        self.assertIn("pg_try_advisory_lock", sql_text)
        self.assertIn("pg_advisory_unlock", sql_text)
        self.assertTrue(conn.closed)


class RadarReviewNotifierTests(unittest.IsolatedAsyncioTestCase):
    def test_notification_text_matches_admin_message_format(self):
        self.assertEqual(
            radar_review_notification_text(2, 5),
            "🔔 Radar\n\n"
            "2 new items are ready for review.\n\n"
            "Pending review: 5\n\n"
            "/radar_review",
        )

    def make_notifier(self, *, totals, admin_ids=(101, 202), sent=None, now=None, send_message=None):
        totals_iter = iter(totals)
        sent = sent if sent is not None else []
        now = now if now is not None else {"value": 0}

        async def default_send_message(*, chat_id, text):
            sent.append((chat_id, text))

        return RadarReviewNotifier(
            admin_ids=list(admin_ids),
            send_message=send_message or default_send_message,
            pending_review_count=lambda: next(totals_iter),
            time_func=lambda: now["value"],
        ), sent, now

    async def test_three_new_items_notify_all_admins_once(self):
        notifier, sent, _now = self.make_notifier(totals=[5, 8])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 0)
        self.assertEqual(sent, [])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 2)
        self.assertEqual([chat_id for chat_id, _ in sent], [101, 202])
        self.assertIn("3 new items are ready for review.", sent[0][1])
        self.assertIn("Pending review: 8", sent[0][1])
        self.assertEqual(notifier.acknowledged_pending_review_count, 8)

    async def test_one_or_two_new_items_do_not_notify_before_window(self):
        notifier, sent, now = self.make_notifier(totals=[5, 6, 7])

        await notifier.notify_if_pending_increased(new_items_hint=0)
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=1), 0)
        now["value"] = 60
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=1), 0)
        self.assertEqual(sent, [])

    async def test_time_window_notifies_waiting_single_item(self):
        notifier, sent, now = self.make_notifier(totals=[1, 1])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=1), 0)
        now["value"] = 30 * 60
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 2)
        self.assertIn("1 new items are ready for review.", sent[0][1])
        self.assertIn("Pending review: 1", sent[0][1])

    async def test_time_window_is_measured_from_previous_completed_notification(self):
        notifier, sent, now = self.make_notifier(totals=[3, 4, 4])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 2)
        sent.clear()
        now["value"] = 10 * 60
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=1), 0)
        self.assertEqual(sent, [])

        now["value"] = 30 * 60
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 2)
        self.assertIn("1 new items are ready for review.", sent[0][1])

    async def test_no_duplicate_notification_when_count_is_unchanged_after_delivery(self):
        notifier, sent, _now = self.make_notifier(totals=[5, 8, 8])

        await notifier.notify_if_pending_increased(new_items_hint=0)
        await notifier.notify_if_pending_increased(new_items_hint=3)
        sent.clear()
        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 0)
        self.assertEqual(sent, [])

    async def test_all_failed_deliveries_are_retried_next_cycle(self):
        attempts = []

        async def send_message(*, chat_id, text):
            attempts.append((chat_id, text))
            raise RuntimeError("temporary telegram failure")

        notifier, _sent, _now = self.make_notifier(
            totals=[3, 3],
            send_message=send_message,
        )

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 0)
        self.assertEqual([chat_id for chat_id, _ in attempts], [101, 202])
        self.assertEqual(notifier.acknowledged_pending_review_count, 0)

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 0)
        self.assertEqual([chat_id for chat_id, _ in attempts], [101, 202, 101, 202])
        self.assertEqual(notifier.acknowledged_pending_review_count, 0)

    async def test_partial_failure_retries_only_failed_admin_without_duplicates(self):
        attempts = []
        failures = {202}

        async def send_message(*, chat_id, text):
            attempts.append((chat_id, text))
            if chat_id in failures:
                failures.remove(chat_id)
                raise RuntimeError("temporary telegram failure")

        notifier, _sent, _now = self.make_notifier(
            totals=[3, 3],
            send_message=send_message,
        )

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 1)
        self.assertEqual([chat_id for chat_id, _ in attempts], [101, 202])
        self.assertEqual(notifier.acknowledged_pending_review_count, 0)

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 1)
        self.assertEqual([chat_id for chat_id, _ in attempts], [101, 202, 202])
        self.assertEqual(notifier.acknowledged_pending_review_count, 3)

    async def test_acknowledged_count_advances_only_after_all_admins_receive_notification(self):
        failures = {202}

        async def send_message(*, chat_id, text):
            if chat_id in failures:
                failures.remove(chat_id)
                raise RuntimeError("temporary telegram failure")

        notifier, _sent, _now = self.make_notifier(
            totals=[4, 4],
            send_message=send_message,
        )

        await notifier.notify_if_pending_increased(new_items_hint=4)
        self.assertEqual(notifier.acknowledged_pending_review_count, 0)

        await notifier.notify_if_pending_increased(new_items_hint=0)
        self.assertEqual(notifier.acknowledged_pending_review_count, 4)

    async def test_existing_backlog_on_first_observation_does_not_notify(self):
        notifier, sent, _now = self.make_notifier(totals=[4])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 0)
        self.assertEqual(sent, [])
        self.assertEqual(notifier.acknowledged_pending_review_count, 4)

    async def test_new_items_created_during_first_cycle_notify_when_batch_threshold_is_met(self):
        notifier, sent, _now = self.make_notifier(totals=[4])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 2)
        self.assertIn("3 new items are ready for review.", sent[0][1])
        self.assertEqual(notifier.acknowledged_pending_review_count, 4)

    async def test_pending_count_decrease_resets_baseline_for_later_new_items(self):
        notifier, sent, _now = self.make_notifier(totals=[5, 3, 6])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 0)
        self.assertEqual(notifier.acknowledged_pending_review_count, 5)

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 0)
        self.assertEqual(notifier.acknowledged_pending_review_count, 3)

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=0), 2)
        self.assertIn("3 new items are ready for review.", sent[0][1])
        self.assertIn("Pending review: 6", sent[0][1])
        self.assertEqual(notifier.acknowledged_pending_review_count, 6)

    async def test_empty_admin_ids_produces_no_exception_and_advances_acknowledgement(self):
        notifier, _sent, _now = self.make_notifier(totals=[3], admin_ids=[])

        self.assertEqual(await notifier.notify_if_pending_increased(new_items_hint=3), 0)
        self.assertEqual(notifier.acknowledged_pending_review_count, 3)


if __name__ == "__main__":
    unittest.main()
