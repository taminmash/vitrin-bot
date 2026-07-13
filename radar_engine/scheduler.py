from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import os
from time import monotonic
from typing import Awaitable, Callable

from radar_engine.ai.engine import AIReport, RadarAIEngine
from radar_engine.classification.engine import ClassificationReport, RadarClassificationEngine
from radar_engine.pipeline.engine import PipelineReport, RadarCandidatePipeline
from radar_engine.review.storage import load_review_queue
from radar_engine.source_manager import IngestionReport, build_default_source_manager


logger = logging.getLogger(__name__)

DEFAULT_FETCH_INTERVAL_MINUTES = 15
MIN_FETCH_INTERVAL_MINUTES = 1


@dataclass
class RadarFetchCycleReport:
    source_key: str = "boe"
    fetched: int = 0
    skipped_duplicate: int = 0
    inserted_raw: int = 0
    candidate_created: int = 0
    ai_completed: int = 0
    classification_completed: int = 0
    queued_for_review: int = 0
    duration_seconds: float = 0.0
    skipped: bool = False
    failed: bool = False
    errors: list[str] = field(default_factory=list)


AsyncStage = Callable[[], Awaitable[object]]


def fetch_interval_minutes_from_env(value: str | None = None) -> int:
    raw = os.getenv("RADAR_FETCH_INTERVAL_MINUTES") if value is None else value
    if not raw:
        return DEFAULT_FETCH_INTERVAL_MINUTES
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(
            "Invalid RADAR_FETCH_INTERVAL_MINUTES=%r; using default %s",
            raw,
            DEFAULT_FETCH_INTERVAL_MINUTES,
        )
        return DEFAULT_FETCH_INTERVAL_MINUTES
    if parsed < MIN_FETCH_INTERVAL_MINUTES:
        logger.warning(
            "RADAR_FETCH_INTERVAL_MINUTES=%r is below minimum %s; using minimum",
            raw,
            MIN_FETCH_INTERVAL_MINUTES,
        )
        return MIN_FETCH_INTERVAL_MINUTES
    return parsed


def _default_ingest_stage(source_key: str):
    async def ingest():
        manager = build_default_source_manager()
        return await manager.ingest_source(source_key)

    return ingest


def _default_pipeline_stage(limit: int):
    async def run_pipeline():
        return await asyncio.to_thread(RadarCandidatePipeline().run, limit=limit)

    return run_pipeline


def _default_ai_stage(limit: int):
    async def run_ai():
        return await asyncio.to_thread(RadarAIEngine().run, limit=limit)

    return run_ai


def _default_classification_stage(limit: int):
    async def run_classification():
        return await asyncio.to_thread(RadarClassificationEngine().run, limit=limit)

    return run_classification


def _default_review_queue_stage(limit: int):
    async def load_queue():
        return await asyncio.to_thread(load_review_queue, limit=limit)

    return load_queue


class RadarBOEIngestionScheduler:
    def __init__(
        self,
        *,
        interval_minutes: int | None = None,
        source_key: str = "boe",
        stage_limit: int = 50,
        ingest_stage: AsyncStage | None = None,
        pipeline_stage: AsyncStage | None = None,
        ai_stage: AsyncStage | None = None,
        classification_stage: AsyncStage | None = None,
        review_queue_stage: AsyncStage | None = None,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.interval_minutes = interval_minutes or fetch_interval_minutes_from_env()
        self.interval_seconds = max(1, int(self.interval_minutes * 60))
        self.source_key = source_key
        self.stage_limit = max(1, min(int(stage_limit), 200))
        self.ingest_stage = ingest_stage or _default_ingest_stage(source_key)
        self.pipeline_stage = pipeline_stage or _default_pipeline_stage(self.stage_limit)
        self.ai_stage = ai_stage or _default_ai_stage(self.stage_limit)
        self.classification_stage = classification_stage or _default_classification_stage(self.stage_limit)
        self.review_queue_stage = review_queue_stage or _default_review_queue_stage(self.stage_limit)
        self.sleep_func = sleep_func
        self._running = False
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def is_running_cycle(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self.run_forever())
        logger.info("Radar scheduler started")

    async def stop(self) -> None:
        self._stop_event.set()
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            await self.run_once()
            if self._stop_event.is_set():
                break
            await self.sleep_func(self.interval_seconds)

    async def run_once(self) -> RadarFetchCycleReport:
        if self._running:
            logger.info("Previous fetch cycle still running.")
            return RadarFetchCycleReport(source_key=self.source_key, skipped=True)

        self._running = True
        started_at = monotonic()
        report = RadarFetchCycleReport(source_key=self.source_key)
        try:
            ingestion = await self.ingest_stage()
            self._apply_ingestion(report, ingestion)

            pipeline = await self.pipeline_stage()
            self._apply_pipeline(report, pipeline)

            ai = await self.ai_stage()
            self._apply_ai(report, ai)

            classification = await self.classification_stage()
            self._apply_classification(report, classification)

            review_items = await self.review_queue_stage()
            report.queued_for_review = len(review_items or [])
        except Exception as error:
            report.failed = True
            report.errors.append(str(error))
            logger.exception("Radar BOE fetch cycle failed")
        finally:
            report.duration_seconds = monotonic() - started_at
            self._running = False
            self._log_report(report)
        return report

    def _apply_ingestion(self, report: RadarFetchCycleReport, ingestion) -> None:
        if not isinstance(ingestion, IngestionReport):
            return
        report.fetched = ingestion.fetched_count
        report.skipped_duplicate = ingestion.duplicate_count
        report.inserted_raw = ingestion.inserted_count
        report.errors.extend(ingestion.errors)

    def _apply_pipeline(self, report: RadarFetchCycleReport, pipeline) -> None:
        if not isinstance(pipeline, PipelineReport):
            return
        report.candidate_created = pipeline.created_count
        report.errors.extend(pipeline.errors)

    def _apply_ai(self, report: RadarFetchCycleReport, ai) -> None:
        if not isinstance(ai, AIReport):
            return
        report.ai_completed = ai.completed
        report.errors.extend(ai.errors)

    def _apply_classification(self, report: RadarFetchCycleReport, classification) -> None:
        if not isinstance(classification, ClassificationReport):
            return
        report.classification_completed = classification.completed
        report.errors.extend(classification.errors)

    def _log_report(self, report: RadarFetchCycleReport) -> None:
        if report.skipped:
            return
        logger.info(
            "Radar BOE cycle metrics: Fetched=%s Skipped duplicate=%s Inserted raw=%s "
            "Candidate created=%s AI completed=%s Classification completed=%s "
            "Queued for review=%s Cycle duration=%.2fs",
            report.fetched,
            report.skipped_duplicate,
            report.inserted_raw,
            report.candidate_created,
            report.ai_completed,
            report.classification_completed,
            report.queued_for_review,
            report.duration_seconds,
        )


async def start_radar_scheduler(application) -> None:
    scheduler = RadarBOEIngestionScheduler()
    application.bot_data["radar_boe_scheduler"] = scheduler
    scheduler.start()


async def stop_radar_scheduler(application) -> None:
    scheduler = application.bot_data.get("radar_boe_scheduler")
    if scheduler:
        await scheduler.stop()
