from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.review.models import RadarSummaryForReview


PROMOTION_STATUS_VALUES = ("completed",)
RADAR_READY_STATUS = "ready"


def _required_text(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def validate_promotion_status(status: str) -> str:
    cleaned = _required_text(status, "promotion_status")
    if cleaned not in PROMOTION_STATUS_VALUES:
        raise ValueError("promotion_status must be completed")
    return cleaned


@dataclass
class ApprovedPromotionSource:
    candidate_id: str
    review_id: str
    review_status: str
    candidate: RadarCandidate
    summary: RadarSummaryForReview
    classification: RadarClassificationResult
    already_promoted: bool = False
    promotion_id: str | None = None
    radar_item_id: str | None = None

    def __post_init__(self) -> None:
        self.candidate_id = _required_text(self.candidate_id, "candidate_id")
        self.review_id = _required_text(self.review_id, "review_id")
        self.review_status = _required_text(self.review_status, "review_status")
        if self.review_status != "approved":
            raise ValueError("review_status must be approved")
        if self.promotion_id is not None:
            self.promotion_id = str(self.promotion_id).strip() or None
        if self.radar_item_id is not None:
            self.radar_item_id = str(self.radar_item_id).strip() or None
        self.already_promoted = bool(self.already_promoted or self.promotion_id or self.radar_item_id)


@dataclass
class MappedRadarItemPayload:
    fields: dict[str, Any]
    content_status: str = RADAR_READY_STATUS

    def __post_init__(self) -> None:
        if self.content_status != RADAR_READY_STATUS:
            raise ValueError("promoted Radar item status must be ready")
        if not isinstance(self.fields, dict):
            raise ValueError("fields must be a dictionary")


@dataclass
class PromotionResult:
    candidate_id: str
    status: str
    radar_item_id: str | None = None
    promotion_id: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def created(self) -> bool:
        return self.status == "created"

    @property
    def already_promoted(self) -> bool:
        return self.status == "already_promoted"


@dataclass
class PromotionReport:
    loaded: int = 0
    processed: int = 0
    created: int = 0
    already_promoted: int = 0
    rejected: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
