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
from radar_engine.pipeline.actionability_backfill import ActionabilityBackfillReport, backfill_actionability
from radar_engine.source_manager import IngestionReport, build_default_source_manager
from radar_engine.source_config import source_interval_minutes
from radar_engine.urgent import UrgentAutoPublicationEngine, UrgentPublicationReport


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
REVIEW_NOTIFICATION_BATCH_SIZE = 3
REVIEW_NOTIFICATION_WINDOW_SECONDS = 30 * 60
ADVISORY_LOCK_NAME = "radar_scheduler:boe"
FALSE_ENV_VALUES = {"0", "false", "no", "off"}


@dataclass
class RadarFetchCycleReport:
    source_key: str = "boe"
    fetched: int = 0
    skipped_duplicate: int = 0
    inserted_raw: int = 0
    candidate_created: int = 0
    actionability_backfill_evaluated: int = 0
    actionability_backfill_passed: int = 0
    actionability_backfill_rejected: int = 0
    actionability_backfill_remaining: int = 0
    ai_completed: int = 0
    ai_processed: int = 0
    ai_failed: int = 0
    ai_postponed: int = 0
    classification_completed: int = 0
    classification_postponed: int = 0
    queued_for_review: int = 0
    urgent_evaluated: int = 0
    urgent_published: int = 0
    urgent_fallback_review: int = 0
    duration_seconds: float = 0.0
    skipped: bool = False
    failed: bool = False
    errors: list[str] = field(default_factory=list)


AsyncStage = Callable[[], Awaitable[object]]
LockFactory = Callable[[], AbstractContextManager[bool]]
ReviewNotificationStage = Callable[[int], Awaitable[object]]
UrgentPublicationStage = Callable[[], Awaitable[object]]


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
        primary = await manager.ingest_source(source_key)
        now = monotonic()
        last_runs = getattr(_default_ingest_stage, "_job_source_last_runs", {})
        for job_key in manager.source_keys():
            if job_key == source_key:
                continue
            interval = source_interval_minutes(job_key) * 60
            if now - last_runs.get(job_key, float("-inf")) < interval:
                continue
            # Each connector is isolated: one failure is recorded but never prevents
            # another source or the existing downstream pipeline from running.
            report = await manager.ingest_source(job_key)
            last_runs[job_key] = now
            logger.info(
                "Radar job source cycle source=%s fetched=%s normalized=%s inserted=%s "
                "duplicates=%s updated=%s failed=%s",
                job_key,
                report.fetched_count,
                report.normalized_count,
                report.inserted_count,
                report.duplicate_count,
                report.updated_count,
                report.failed_count,
            )
            primary.fetched_count += report.fetched_count
            primary.normalized_count += report.normalized_count
            primary.inserted_count += report.inserted_count
            primary.duplicate_count += report.duplicate_count
            primary.updated_count += report.updated_count
            primary.failed_count += report.failed_count
            primary.errors.extend(f"{job_key}: {error}" for error in report.errors)
        _default_ingest_stage._job_source_last_runs = last_runs
        return primary

    return ingest


def _default_pipeline_stage(limit: int):
    async def run_pipeline():
        return await asyncio.to_thread(RadarCandidatePipeline().run, limit=limit)

    return run_pipeline


def _default_ai_stage(limit: int, request_delay_seconds: float = 0.0):
    async def run_ai():
        return await asyncio.to_thread(RadarAIEngine(request_delay_seconds=request_delay_seconds).run, limit=limit)

    return run_ai


def _default_actionability_backfill_stage(limit: int):
    async def run_backfill():
        return await asyncio.to_thread(backfill_actionability, limit=limit)

    return run_backfill


async def _empty_actionability_backfill_stage():
    return ActionabilityBackfillReport()


def _default_classification_stage(limit: int, request_delay_seconds: float = 0.0):
    async def run_classification():
        return await asyncio.to_thread(
            RadarClassificationEngine(request_delay_seconds=request_delay_seconds).run,
            limit=limit,
        )

    return run_classification


async def _empty_urgent_publication_stage():
    return UrgentPublicationReport()


def _default_urgent_publication_stage(bot, admin_ids, limit: int):
    async def notify_admins(item, radar_item, decision, result):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from radar_engine.urgent import urgent_admin_notification_text

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("مشاهده آیتم منتشرشده", callback_data=f"admin_radar:item:{radar_item['id']}")],
                [InlineKeyboardButton("صف بازبینی Radar", callback_data="admin_radar:review:list")],
            ]
        )
        sent = 0
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=urgent_admin_notification_text(item, decision),
                    reply_markup=keyboard,
                )
                sent += 1
            except Exception:
                logger.exception("Could not notify admin_id=%s about urgent publication", admin_id)
        return sent

    async def run_urgent_publication():
        from config_v2 import CHANNEL_VITRIN, CHANNEL_VITRIN_USERNAME
        from radar_engine.publication.engine import RadarPublicationEngine
        from radar_engine.publication.publisher import RadarTelegramPublisher

        publisher = RadarTelegramPublisher(bot, channel_id=CHANNEL_VITRIN, channel_username=CHANNEL_VITRIN_USERNAME)
        engine = UrgentAutoPublicationEngine(
            publisher=RadarPublicationEngine(publisher=publisher),
            admin_notifier=notify_admins,
        )
        return await engine.run(limit=limit)

    return run_urgent_publication


def radar_review_notification_text(new_count: int, pending_total: int) -> str:
    return (
        "🔔 Radar\n\n"
        f"{new_count} new items are ready for review.\n\n"
        f"Pending review: {pending_total}\n\n"
        "/radar_review"
    )


class RadarReviewNotifier:
    def __init__(
        self,
        *,
        admin_ids: list[int] | tuple[int, ...],
        send_message,
        pending_review_count: Callable[[], int],
        batch_size: int = REVIEW_NOTIFICATION_BATCH_SIZE,
        notification_window_seconds: int = REVIEW_NOTIFICATION_WINDOW_SECONDS,
        time_func: Callable[[], float] = monotonic,
    ):
        self.admin_ids = tuple(int(admin_id) for admin_id in admin_ids)
        self.send_message = send_message
        self.pending_review_count = pending_review_count
        self.batch_size = max(1, int(batch_size))
        self.notification_window_seconds = max(1, int(notification_window_seconds))
        self.time_func = time_func
        self._acknowledged_pending_review_count: int | None = None
        self._pending_notification: dict[str, object] | None = None
        self._unnotified_since: float | None = None
        self._last_completed_notification_at: float | None = None

    @property
    def acknowledged_pending_review_count(self) -> int | None:
        return self._acknowledged_pending_review_count

    async def notify_if_pending_increased(self, new_items_hint: int = 0) -> int:
        pending_total = max(0, int(self.pending_review_count()))
        if self._pending_notification:
            return await self.retry_pending_delivery(pending_total=pending_total)

        acknowledged_total = self._acknowledged_pending_review_count
        if acknowledged_total is None:
            new_count = min(max(int(new_items_hint or 0), 0), pending_total)
            self._acknowledged_pending_review_count = pending_total - new_count
        elif pending_total < acknowledged_total:
            self._acknowledged_pending_review_count = pending_total
            self._unnotified_since = None
            return 0
        elif pending_total > acknowledged_total:
            new_count = pending_total - acknowledged_total
        else:
            self._unnotified_since = None
            return 0

        if new_count <= 0:
            self._acknowledged_pending_review_count = pending_total
            self._unnotified_since = None
            return 0

        if not self._should_notify(new_count):
            return 0

        self._pending_notification = {
            "new_count": new_count,
            "target_count": pending_total,
            "delivered_admin_ids": set(),
        }
        return await self._deliver_pending_notification()

    async def retry_pending_delivery(self, pending_total: int | None = None) -> int:
        if not self._pending_notification:
            return 0
        if pending_total is None:
            pending_total = max(0, int(self.pending_review_count()))
        target_count = int(self._pending_notification["target_count"])
        if pending_total < target_count:
            self._pending_notification = None
            self._acknowledged_pending_review_count = pending_total
            self._unnotified_since = None
            return 0
        return await self._deliver_pending_notification()

    def _should_notify(self, new_count: int) -> bool:
        now = self.time_func()
        if new_count >= self.batch_size:
            return True
        if self._unnotified_since is None:
            self._unnotified_since = now
        reference_time = self._last_completed_notification_at
        if reference_time is None:
            reference_time = self._unnotified_since
        return now - reference_time >= self.notification_window_seconds

    async def _deliver_pending_notification(self) -> int:
        if not self._pending_notification:
            return 0

        target_count = int(self._pending_notification["target_count"])
        new_count = int(self._pending_notification["new_count"])
        delivered_admin_ids = self._pending_notification["delivered_admin_ids"]

        if not self.admin_ids:
            self._acknowledged_pending_review_count = target_count
            self._pending_notification = None
            self._unnotified_since = None
            self._last_completed_notification_at = self.time_func()
            return 0

        text = radar_review_notification_text(new_count, target_count)
        sent = 0
        for admin_id in self.admin_ids:
            if admin_id in delivered_admin_ids:
                continue
            try:
                await self.send_message(chat_id=admin_id, text=text)
                delivered_admin_ids.add(admin_id)
                sent += 1
            except Exception:
                logger.exception("Could not send Radar review notification to admin_id=%s", admin_id)

        if all(admin_id in delivered_admin_ids for admin_id in self.admin_ids):
            self._acknowledged_pending_review_count = target_count
            self._pending_notification = None
            self._unnotified_since = None
            self._last_completed_notification_at = self.time_func()
        return sent


def pending_review_count() -> int:
    from radar_engine.review.storage import review_status_report

    return review_status_report().pending


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
        actionability_backfill_stage: AsyncStage | None = None,
        ai_stage: AsyncStage | None = None,
        classification_stage: AsyncStage | None = None,
        urgent_publication_stage: UrgentPublicationStage | None = None,
        review_notification_stage: ReviewNotificationStage | None = None,
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
        if actionability_backfill_stage is not None:
            self.actionability_backfill_stage = actionability_backfill_stage
        elif pipeline_stage is not None:
            # Explicitly injected stages are isolated by default (primarily tests/tools).
            self.actionability_backfill_stage = _empty_actionability_backfill_stage
        else:
            self.actionability_backfill_stage = _default_actionability_backfill_stage(self.stage_limit)
        self.ai_stage = ai_stage or _default_ai_stage(self.ai_batch_limit, self.ai_request_delay_seconds)
        self.classification_stage = classification_stage or _default_classification_stage(
            self.ai_batch_limit,
            self.ai_request_delay_seconds,
        )
        self.urgent_publication_stage = urgent_publication_stage or _empty_urgent_publication_stage
        self.review_notification_stage = review_notification_stage
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
                    await self._notify_review_queue(report, retry_pending_only=True)
                    return report

                pipeline = await self.pipeline_stage()
                self._apply_pipeline(report, pipeline)

                backfill = await self.actionability_backfill_stage()
                self._apply_actionability_backfill(report, backfill)

                ai = await self.ai_stage()
                self._apply_ai(report, ai)
                if isinstance(ai, AIReport) and ai.stopped_early:
                    await self._notify_review_queue(report)
                    return report

                classification = await self.classification_stage()
                self._apply_classification(report, classification)
                report.queued_for_review = report.classification_completed
                urgent = await self.urgent_publication_stage()
                self._apply_urgent_publication(report, urgent)
                await self._notify_review_queue(report)
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

    def _apply_actionability_backfill(self, report: RadarFetchCycleReport, backfill) -> None:
        if not isinstance(backfill, ActionabilityBackfillReport):
            return
        report.actionability_backfill_evaluated = backfill.evaluated
        report.actionability_backfill_passed = backfill.passed
        report.actionability_backfill_rejected = backfill.rejected
        report.actionability_backfill_remaining = backfill.remaining
        report.errors.extend(backfill.errors)

    def _apply_classification(self, report: RadarFetchCycleReport, classification) -> None:
        if not isinstance(classification, ClassificationReport):
            return
        report.classification_completed = classification.completed
        report.classification_postponed = classification.remaining
        report.errors.extend(classification.errors)

    def _apply_urgent_publication(self, report: RadarFetchCycleReport, urgent) -> None:
        if not isinstance(urgent, UrgentPublicationReport):
            return
        report.urgent_evaluated = urgent.evaluated
        report.urgent_published = urgent.published
        report.urgent_fallback_review = urgent.fallback_review
        report.errors.extend(urgent.errors)

    async def _notify_review_queue(self, report: RadarFetchCycleReport, *, retry_pending_only: bool = False) -> None:
        if not self.review_notification_stage:
            return
        try:
            if retry_pending_only:
                notifier = getattr(self.review_notification_stage, "__self__", None)
                retry_pending_delivery = getattr(notifier, "retry_pending_delivery", None)
                if retry_pending_delivery:
                    await retry_pending_delivery()
                return
            await self.review_notification_stage(report.queued_for_review)
        except Exception as error:
            report.errors.append(str(error))
            logger.exception("Radar review notification failed")

    def _log_report(self, report: RadarFetchCycleReport) -> None:
        if report.skipped:
            return
        logger.info(
            "Radar BOE cycle metrics: Fetched=%s Skipped duplicate=%s Inserted raw=%s "
            "Candidate created=%s Actionability backfill evaluated=%s passed=%s rejected=%s remaining=%s "
            "AI processed=%s AI completed=%s AI failed=%s "
            "AI postponed=%s Classification completed=%s Classification postponed=%s "
            "Remaining AI queue estimate=%s "
            "Queued for review=%s Urgent evaluated=%s published=%s fallback_review=%s "
            "Cycle duration=%.2fs",
            report.fetched,
            report.skipped_duplicate,
            report.inserted_raw,
            report.candidate_created,
            report.actionability_backfill_evaluated,
            report.actionability_backfill_passed,
            report.actionability_backfill_rejected,
            report.actionability_backfill_remaining,
            report.ai_processed,
            report.ai_completed,
            report.ai_failed,
            report.ai_postponed,
            report.classification_completed,
            report.classification_postponed,
            report.ai_postponed,
            report.queued_for_review,
            report.urgent_evaluated,
            report.urgent_published,
            report.urgent_fallback_review,
            report.duration_seconds,
        )


async def start_radar_scheduler(application) -> None:
    if not auto_ingestion_enabled():
        logger.info("Radar automatic ingestion is disabled")
        return
    existing = application.bot_data.get("radar_boe_scheduler")
    if existing:
        return
    from config_v2 import ADMIN_IDS

    notifier = RadarReviewNotifier(
        admin_ids=ADMIN_IDS,
        send_message=application.bot.send_message,
        pending_review_count=pending_review_count,
    )
    scheduler = RadarBOEIngestionScheduler(
        review_notification_stage=notifier.notify_if_pending_increased,
        urgent_publication_stage=_default_urgent_publication_stage(application.bot, ADMIN_IDS, 50),
    )
    application.bot_data["radar_boe_scheduler"] = scheduler
    application.bot_data["radar_review_notifier"] = notifier
    scheduler.start()


async def stop_radar_scheduler(application) -> None:
    scheduler = application.bot_data.get("radar_boe_scheduler")
    if scheduler:
        await scheduler.stop()
