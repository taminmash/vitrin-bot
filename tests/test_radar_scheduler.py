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
    advisory_lock_key,
    ai_batch_limit_from_env,
    ai_request_delay_seconds_from_env,
    auto_ingestion_enabled,
    fetch_interval_minutes_from_env,
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

    async def test_scheduler_starts_and_stores_instance(self):
        class FakeScheduler:
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

            def __init__(self):
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
        self.assertIn(".post_init(start_radar_scheduler)", bot_text)
        self.assertIn(".post_shutdown(stop_radar_scheduler)", bot_text)

    async def test_pipeline_called_once_per_cycle_and_metrics_collected(self):
        calls = []

        async def ingest():
            return IngestionReport("boe", fetched_count=3, inserted_count=2, duplicate_count=1)

        async def pipeline():
            calls.append("pipeline")
            return PipelineReport(created_count=2)

        scheduler = RadarBOEIngestionScheduler(
            interval_minutes=15,
            ingest_stage=ingest,
            pipeline_stage=pipeline,
            ai_stage=lambda: immediate_report(AIReport(completed=2)),
            classification_stage=lambda: immediate_report(ClassificationReport(completed=2)),
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertEqual(calls, ["pipeline"])
        self.assertEqual(report.fetched, 3)
        self.assertEqual(report.skipped_duplicate, 1)
        self.assertEqual(report.inserted_raw, 2)
        self.assertEqual(report.candidate_created, 2)
        self.assertEqual(report.ai_completed, 2)
        self.assertEqual(report.classification_completed, 2)
        self.assertEqual(report.queued_for_review, 2)

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
            lock_factory=lambda: FakeLock(True),
        )
        report = await scheduler.run_once()
        self.assertTrue(report.failed)
        self.assertEqual(calls, [])

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


if __name__ == "__main__":
    unittest.main()
