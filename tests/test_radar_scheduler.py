import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from radar_engine.ai.engine import AIReport
from radar_engine.classification.engine import ClassificationReport
from radar_engine.pipeline.engine import PipelineReport
from radar_engine.scheduler import (
    DEFAULT_FETCH_INTERVAL_MINUTES,
    RadarBOEIngestionScheduler,
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


class RadarSchedulerTests(unittest.IsolatedAsyncioTestCase):
    def test_interval_defaults_and_env_override(self):
        self.assertEqual(fetch_interval_minutes_from_env(""), DEFAULT_FETCH_INTERVAL_MINUTES)
        self.assertEqual(fetch_interval_minutes_from_env("15"), 15)
        self.assertEqual(fetch_interval_minutes_from_env("0"), 1)
        self.assertEqual(fetch_interval_minutes_from_env("bad"), DEFAULT_FETCH_INTERVAL_MINUTES)

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
            review_queue_stage=lambda: immediate_report([object(), object()]),
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
            review_queue_stage=lambda: immediate_report([]),
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
            review_queue_stage=lambda: immediate_report([]),
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
            review_queue_stage=lambda: immediate_report([object()]),
        )
        first = await scheduler.run_once()
        second = await scheduler.run_once()
        self.assertTrue(first.failed)
        self.assertIn("BOE unavailable", first.errors[0])
        self.assertFalse(second.failed)
        self.assertEqual(second.inserted_raw, 1)
        self.assertEqual(second.queued_for_review, 1)
        self.assertEqual(attempts, 2)

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
            review_queue_stage=lambda: immediate_report([]),
            sleep_func=sleep_once,
        )
        await scheduler.run_forever()
        self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
