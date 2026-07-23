from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import os
from urllib.parse import urlparse

from radar_engine.promotion.mapper import map_approved_source_to_radar_item, validate_mapped_payload
from radar_engine.publication.models import EligiblePublicationItem, PublicationResult


logger = logging.getLogger(__name__)
TRUE_VALUES = {"1", "true", "yes", "on"}
AUTO_PUBLISH_ACTOR_ID = None


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


@dataclass(frozen=True)
class UrgentAutoPublishConfig:
    enabled: bool = False
    min_score: int = 90
    min_confidence: float = 0.90
    cooldown_minutes: int = 30
    daily_safety_limit: int = 10

    @classmethod
    def from_env(cls) -> "UrgentAutoPublishConfig":
        return cls(
            enabled=os.getenv("RADAR_URGENT_AUTO_PUBLISH_ENABLED", "false").strip().casefold() in TRUE_VALUES,
            min_score=_bounded_int("RADAR_URGENT_AUTO_PUBLISH_MIN_SCORE", 90, 0, 100),
            min_confidence=_bounded_float("RADAR_URGENT_AUTO_PUBLISH_MIN_CONFIDENCE", 0.90, 0.0, 1.0),
            cooldown_minutes=_bounded_int("RADAR_URGENT_AUTO_PUBLISH_COOLDOWN_MINUTES", 30, 5, 1440),
            daily_safety_limit=_bounded_int("RADAR_URGENT_AUTO_PUBLISH_DAILY_SAFETY_LIMIT", 10, 1, 100),
        )


@dataclass(frozen=True)
class UrgentEligibilityDecision:
    eligible: bool
    reasons: tuple[str, ...]
    score: int | None = None
    confidence: float | None = None


@dataclass
class UrgentPublicationReport:
    evaluated: int = 0
    eligible: int = 0
    published: int = 0
    fallback_review: int = 0
    failed: int = 0
    notified_admins: int = 0
    errors: list[str] = field(default_factory=list)


def _valid_url(value: str | None) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_current(item, now: datetime) -> bool:
    candidate = item.candidate
    if candidate.valid_until and candidate.valid_until <= now:
        return False
    if candidate.valid_from and candidate.valid_from > now:
        return False
    if candidate.valid_until and candidate.valid_until > now:
        return True
    return bool(candidate.published_at and candidate.published_at >= now - timedelta(hours=24))


def evaluate_urgent_candidate(
    item,
    config: UrgentAutoPublishConfig,
    *,
    now: datetime | None = None,
    trusted_source: bool = True,
    cooldown_active: bool = False,
    daily_limit_reached: bool = False,
) -> UrgentEligibilityDecision:
    now = now or datetime.now()
    candidate = item.candidate
    classification = item.classification
    summary = item.summary
    metadata = candidate.metadata or {}
    gate = metadata.get("actionability_gate") or {}
    score = metadata.get("actionability_score")
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = None
    confidence = float(classification.confidence)
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("disabled")
    if classification.primary_category != "alert":
        reasons.append("not_alert")
    if classification.urgency != "urgent":
        reasons.append("not_highest_urgency")
    if confidence < config.min_confidence:
        reasons.append("low_confidence")
    if score is None or score < config.min_score:
        reasons.append("low_actionability_score")
    if gate.get("passed") is not True:
        reasons.append("actionability_gate_failed")
    if not (candidate.title or "").strip():
        reasons.append("missing_title")
    if not (summary.summary or candidate.body or "").strip():
        reasons.append("missing_summary")
    if not (candidate.source_name or "").strip():
        reasons.append("missing_source")
    if not _valid_url(candidate.source_url):
        reasons.append("invalid_source_url")
    if not trusted_source or candidate.source_type != "official" or candidate.trust_level < 4:
        reasons.append("untrusted_source")
    if candidate.candidate_status == "rejected" or metadata.get("rejected") is True:
        reasons.append("rejected")
    if metadata.get("duplicate") is True or metadata.get("is_duplicate") is True:
        reasons.append("duplicate")
    if metadata.get("urgent_auto_publish"):
        reasons.append("already_evaluated")
    if not _is_current(item, now):
        reasons.append("not_current")
    if cooldown_active:
        reasons.append("cooldown")
    if daily_limit_reached:
        reasons.append("daily_safety_limit")
    return UrgentEligibilityDecision(not reasons, tuple(reasons), score, confidence)


def urgent_admin_notification_text(item, decision: UrgentEligibilityDecision) -> str:
    return (
        "🚨 هشدار فوری به‌صورت خودکار منتشر شد\n\n"
        f"عنوان:\n{item.candidate.title}\n\n"
        f"منبع:\n{item.candidate.source_name}\n\n"
        f"امتیاز اهمیت:\n{decision.score}\n\n"
        f"اطمینان دسته‌بندی:\n{decision.confidence:.2f}"
    )


class UrgentAutoPublicationEngine:
    def __init__(
        self,
        *,
        config: UrgentAutoPublishConfig | None = None,
        loader=None,
        trusted_source_checker=None,
        safety_state_loader=None,
        item_preparer=None,
        publisher=None,
        outcome_recorder=None,
        admin_notifier=None,
        now_func=datetime.now,
    ):
        if any(value is None for value in (loader, trusted_source_checker, safety_state_loader, item_preparer, outcome_recorder)):
            from radar_engine.urgent_storage import (
                is_trusted_urgent_source,
                load_urgent_candidates,
                load_urgent_safety_state,
                prepare_urgent_radar_item,
                record_urgent_outcome,
            )

            loader = loader or load_urgent_candidates
            trusted_source_checker = trusted_source_checker or is_trusted_urgent_source
            safety_state_loader = safety_state_loader or load_urgent_safety_state
            item_preparer = item_preparer or prepare_urgent_radar_item
            outcome_recorder = outcome_recorder or record_urgent_outcome
        self.config = config or UrgentAutoPublishConfig.from_env()
        self.loader = loader
        self.trusted_source_checker = trusted_source_checker
        self.safety_state_loader = safety_state_loader
        self.item_preparer = item_preparer
        self.publisher = publisher
        self.outcome_recorder = outcome_recorder
        self.admin_notifier = admin_notifier
        self.now_func = now_func

    async def run(self, limit: int = 50) -> UrgentPublicationReport:
        report = UrgentPublicationReport()
        items = self.loader(limit=max(1, min(int(limit), 200)))
        safety = self.safety_state_loader()
        now = self.now_func()
        for item in items:
            report.evaluated += 1
            decision = evaluate_urgent_candidate(
                item,
                self.config,
                now=now,
                trusted_source=self.trusted_source_checker(item.candidate),
                cooldown_active=bool(safety.get("last_published_at") and safety["last_published_at"] > now - timedelta(minutes=self.config.cooldown_minutes)),
                daily_limit_reached=int(safety.get("published_today") or 0) >= self.config.daily_safety_limit,
            )
            if not decision.eligible:
                report.fallback_review += 1
                continue
            report.eligible += 1
            prepared = None
            try:
                prepared = self.item_preparer(item, decision)
                payload = map_approved_source_to_radar_item(item)
                if validate_mapped_payload(payload):
                    raise ValueError("urgent item could not be rendered as a publishable Radar item")
                if self.publisher is None:
                    raise RuntimeError("urgent publisher is not configured")
                result = await self.publisher.publish_item(EligiblePublicationItem(prepared), published_by=AUTO_PUBLISH_ACTOR_ID)
            except Exception as error:
                if prepared is not None:
                    try:
                        self.outcome_recorder(
                            item,
                            prepared,
                            decision,
                            PublicationResult(str(prepared["id"]), "failed", error=str(error)),
                        )
                    except Exception:
                        logger.exception("Could not persist urgent publication failure")
                report.failed += 1
                report.fallback_review += 1
                report.errors.append(f"{item.candidate_id}: {error}")
                logger.exception("Urgent Radar publication failed for candidate %s", item.candidate_id)
                break
            try:
                self.outcome_recorder(item, prepared, decision, result)
            except Exception as error:
                report.errors.append(f"{item.candidate_id}: outcome audit: {error}")
                logger.exception("Could not persist urgent publication audit")
            if result.published or result.already_published:
                report.published += 1
                logger.info(
                    "Automatic urgent Radar publication candidate_id=%s radar_item_id=%s "
                    "reason=verified_high_confidence_urgent score=%s confidence=%.2f",
                    item.candidate_id,
                    prepared["id"],
                    decision.score,
                    decision.confidence,
                )
                if self.admin_notifier:
                    try:
                        report.notified_admins += int(await self.admin_notifier(item, prepared, decision, result) or 0)
                    except Exception as error:
                        report.errors.append(f"admin notification: {error}")
                        logger.exception("Urgent publication admin notification failed")
            else:
                report.failed += 1
                report.fallback_review += 1
                report.errors.append(f"{item.candidate_id}: {result.status}: {result.error or ''}".strip())
            break
        return report
