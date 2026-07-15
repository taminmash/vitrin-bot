from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from hashlib import sha256
import logging
import os
from time import monotonic
from typing import Awaitable, Callable

from radar_engine.ai.engine import AIReport, RadarAIEngine
from radar_engine.ai.client import selected_ai_provider
from radar_engine.ai.providers import AIConfigurationError
from radar_engine.classification.engine import ClassificationReport, RadarClassificationEngine
from radar_engine.pipeline.engine import PipelineReport, RadarCandidatePipeline
from radar_engine.source_manager import IngestionReport, build_default_source_manager


logger = logging.getLogger(__name__)

DEFAULT_FETCH_INTERVAL_MINUTES = 15
MIN_FETCH_INTERVAL_MINUTES = 1
DEFAULT_AI_BATCH_LIMIT = 10
DEFAULT_GEMINI_AI_BATCH_LIMIT = 1
MIN_AI_BATCH_LIMIT = 1
MAX_AI_BATCH_LIMIT = 10
DEFAULT_AI_REQUEST_DELAY_SECONDS = 1.0
DEFAULT_GEMINI_AI_REQUEST_DELAY_SECONDS = 15.0
MIN_AI_REQUEST_DELAY_SECONDS = 0.0
MAX_AI_REQUEST_DELAY_SECONDS = 60.0
ADVISORY_LOCK_NAME = "radar_scheduler:boe"
FALSE_ENV_VALUES = {"0", "false", "no", "off"}


@dataclass
class RadarFetchCycleReport:
    source_key: str = "boe"
    fetched: int = 0
    skipped_duplicate: int = 0
    inserted_raw: int = 0
    candidate_created: int = 0
    ai_completed: int = 0
    ai_processed: int = 0
    ai_failed: int = 0
    ai_postponed: int = 0
    classification_completed: int = 0
    classification_postponed: int = 0
    queued_for_review: int = 0
    duration_seconds: float = 0.0
    skipped: bool = False
    failed: bool = False
    errors: list[str] = field(default_factory=list)


AsyncStage = Callable[[], Awaitable[object]]
LockFactory = Callable[[], AbstractContextManager[bool]]


def advisory_lock_key(name: str = ADVISORY_LOCK_NAME) -> int:
    digest = sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class PostgresAdvisoryLock:
    def __init__(self, lock_name: str = ADVISORY_LOCK_NAME, connection_factory=None):
        self.lock_name = lock_name
        self.lock_key = advisory_lock_key(lock_name)
        self.connection_factory = connection_factory
        self.conn = None
        self.acquired = False

    def __enter__(self) -> bool:
        if self.connection_factory:
            self.conn = self.connection_factory()
        else:
            from database.db import get_connection

            self.conn = get_connection()
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (self.lock_key,))
            row = cur.fetchone()
        self.acquired = bool(row and row[0])
        return self.acquired

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self.conn and self.acquired:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (self.lock_key,))
        finally:
            if self.conn:
                self.conn.close()
            self.conn = None
            self.acquired = False


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


def auto_ingestion_enabled(value: str | None = None) -> bool:
    raw = os.getenv("RADAR_AUTO_INGESTION_ENABLED") if value is None else value
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().casefold() not in FALSE_ENV_VALUES


def _selected_provider_for_defaults() -> str:
    try:
        return selected_ai_provider()
    except AIConfigurationError:
        return "gemini"


def _default_ai_batch_limit(provider: str | None = None) -> int:
    provider = provider or _selected_provider_for_defaults()
    return DEFAULT_GEMINI_AI_BATCH_LIMIT if provider == "gemini" else DEFAULT_AI_BATCH_LIMIT


def _default_ai_request_delay_seconds(provider: str | None = None) -> float:
    provider = provider or _selected_provider_for_defaults()
    return DEFAULT_GEMINI_AI_REQUEST_DELAY_SECONDS if provider == "gemini" else DEFAULT_AI_REQUEST_DELAY_SECONDS


def ai_batch_limit_from_env(value: str | None = None, provider: str | None = None) -> int:
    raw = os.getenv("RADAR_AI_BATCH_LIMIT") if value is None else value
    if raw is None or str(raw).strip() == "":
        return _default_ai_batch_limit(provider)
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        default = _default_ai_batch_limit(provider)
        logger.warning("Invalid RADAR_AI_BATCH_LIMIT=%r; using default %s", raw, default)
        return default
    return min(MAX_AI_BATCH_LIMIT, max(MIN_AI_BATCH_LIMIT, parsed))


def ai_request_delay_seconds_from_env(value: str | None = None, provider: str | None = None) -> float:
    raw = os.getenv("RADAR_AI_REQUEST_DELAY_SECONDS") if value is None else value
    if raw is None or str(raw).strip() == "":
        return _default_ai_request_delay_seconds(provider)
    try:
        parsed = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(
            "Invalid RADAR_AI_REQUEST_DELAY_SECONDS=%r; using default %s",
            raw,
            _default_ai_request_delay_seconds(provider),
        )
        return _default_ai_request_delay_seconds(provider)
    return min(MAX_AI_REQUEST_DELAY_SECONDS, max(MIN_AI_REQUEST_DELAY_SECONDS, parsed))


def _default_ingest_stage(source_key: str):
    async def ingest():
        manager = build_default_source_manager()
        return await manager.ingest_source(source_key)

    return ingest


def _default_pipeline_stage(limit: int):
    async def run_pipeline():
        return await asyncio.to_thread(RadarCandidatePipeline().run, limit=limit)

    return run_pipeline


def _default_ai_stage(limit: int, request_delay_seconds: float = 0.0):
    async def run_ai():
        return await asyncio.to_thread(RadarAIEngine(request_delay_seconds=request_delay_seconds).run, limit=limit)

    return run_ai


def _default_classification_stage(limit: int, request_delay_seconds: float = 0.0):
    async def run_classification():
        return await asyncio.to_thread(
            RadarClassificationEngine(request_delay_seconds=request_delay_seconds).run,
            limit=limit,
        )

    return run_classification


class RadarBOEIngestionScheduler:
    def __init__(
        self,
        *,
        interval_minutes: int | None = None,
        source_key: str = "boe",
        stage_limit: int = 50,
        ai_batch_limit: int | None = None,
        ai_request_delay_seconds: float | None = None,
        ingest_stage: AsyncStage | None = None,
        pipeline_stage: AsyncStage | None = None,
        ai_stage: AsyncStage | None = None,
        classification_stage: AsyncStage | None = None,
        lock_factory: LockFactory | None = None,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.interval_minutes = interval_minutes or fetch_interval_minutes_from_env()
        self.interval_seconds = max(1, int(self.interval_minutes * 60))
        self.source_key = source_key
        self.stage_limit = max(1, min(int(stage_limit), 200))
        provider = _selected_provider_for_defaults()
        self.ai_batch_limit = ai_batch_limit if ai_batch_limit is not None else ai_batch_limit_from_env(provider=provider)
        self.ai_batch_limit = min(MAX_AI_BATCH_LIMIT, max(MIN_AI_BATCH_LIMIT, int(self.ai_batch_limit)))
        self.ai_request_delay_seconds = (
            ai_request_delay_seconds
            if ai_request_delay_seconds is not None
            else ai_request_delay_seconds_from_env(provider=provider)
        )
        self.ai_request_delay_seconds = min(
            MAX_AI_REQUEST_DELAY_SECONDS,
            max(MIN_AI_REQUEST_DELAY_SECONDS, float(self.ai_request_delay_seconds)),
        )
        self.ingest_stage = ingest_stage or _default_ingest_stage(source_key)
        self.pipeline_stage = pipeline_stage or _default_pipeline_stage(self.stage_limit)
        self.ai_stage = ai_stage or _default_ai_stage(self.ai_batch_limit, self.ai_request_delay_seconds)
        self.classification_stage = classification_stage or _default_classification_stage(
            self.ai_batch_limit,
            self.ai_request_delay_seconds,
        )
        self.lock_factory = lock_factory or (lambda: PostgresAdvisoryLock(ADVISORY_LOCK_NAME))
        self.sleep_func = sleep_func
        self._running = False
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def is_running_cycle(self) -> bool:
        return self._running

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done() and not self._stop_event.is_set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set() or (self._task is not None and self._task.done())

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
            with self.lock_factory() as lock_acquired:
                if not lock_acquired:
                    logger.info("Previous Radar BOE cycle is running in another process.")
                    report.skipped = True
                    return report

                ingestion = await self.ingest_stage()
                self._apply_ingestion(report, ingestion)
                if self._fatal_ingestion_failure(ingestion):
                    report.failed = True
                    logger.error("Radar BOE ingestion failed before fetching any items; skipping downstream stages.")
                    return report

                pipeline = await self.pipeline_stage()
                self._apply_pipeline(report, pipeline)

                ai = await self.ai_stage()
                self._apply_ai(report, ai)
                if isinstance(ai, AIReport) and ai.stopped_early:
                    return report

                classification = await self.classification_stage()
                self._apply_classification(report, classification)
                report.queued_for_review = report.classification_completed
        except Exception as error:
            report.failed = True
            report.errors.append(str(error))
            logger.exception("Radar BOE fetch cycle failed")
        finally:
            report.duration_seconds = monotonic() - started_at
            self._running = False
            self._log_report(report)
        return report

    def _fatal_ingestion_failure(self, ingestion) -> bool:
        if not isinstance(ingestion, IngestionReport):
            return False
        return ingestion.fetched_count == 0 and ingestion.failed_count > 0

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
        report.ai_processed = ai.processed
        report.ai_completed = ai.completed
        report.ai_failed = ai.failed
        report.ai_postponed = ai.remaining
        report.errors.extend(ai.errors)

    def _apply_classification(self, report: RadarFetchCycleReport, classification) -> None:
        if not isinstance(classification, ClassificationReport):
            return
        report.classification_completed = classification.completed
        report.classification_postponed = classification.remaining
        report.errors.extend(classification.errors)

    def _log_report(self, report: RadarFetchCycleReport) -> None:
        if report.skipped:
            return
        logger.info(
            "Radar BOE cycle metrics: Fetched=%s Skipped duplicate=%s Inserted raw=%s "
            "Candidate created=%s AI processed=%s AI completed=%s AI failed=%s "
            "AI postponed=%s Classification completed=%s Classification postponed=%s "
            "Remaining AI queue estimate=%s "
            "Queued for review=%s Cycle duration=%.2fs",
            report.fetched,
            report.skipped_duplicate,
            report.inserted_raw,
            report.candidate_created,
            report.ai_processed,
            report.ai_completed,
            report.ai_failed,
            report.ai_postponed,
            report.classification_completed,
            report.classification_postponed,
            report.ai_postponed,
            report.queued_for_review,
            report.duration_seconds,
        )


async def start_radar_scheduler(application) -> None:
    if not auto_ingestion_enabled():
        logger.info("Radar automatic ingestion is disabled")
        return
    existing = application.bot_data.get("radar_boe_scheduler")
    if existing:
        return
    scheduler = RadarBOEIngestionScheduler()
    application.bot_data["radar_boe_scheduler"] = scheduler
    scheduler.start()


async def stop_radar_scheduler(application) -> None:
    scheduler = application.bot_data.get("radar_boe_scheduler")
    if scheduler:
        await scheduler.stop()
