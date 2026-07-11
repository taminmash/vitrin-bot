from __future__ import annotations

from dataclasses import dataclass, field

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate


REVIEW_STATUS_VALUES = ("pending", "approved", "rejected", "needs_edit")


def _required_text(value, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def validate_review_status(status: str) -> str:
    cleaned = _required_text(status, "review_status")
    if cleaned not in REVIEW_STATUS_VALUES:
        raise ValueError(f"review_status must be one of: {', '.join(REVIEW_STATUS_VALUES)}")
    return cleaned


@dataclass
class RadarSummaryForReview:
    ai_result_id: str
    headline: str
    summary: str
    why_it_matters: str
    confidence: float

    def __post_init__(self) -> None:
        self.ai_result_id = _required_text(self.ai_result_id, "ai_result_id")
        self.headline = _required_text(self.headline, "headline")
        self.summary = _required_text(self.summary, "summary")
        self.why_it_matters = _required_text(self.why_it_matters, "why_it_matters")
        self.confidence = float(self.confidence)
        if not 0 <= self.confidence <= 1:
            raise ValueError("summary confidence must be between 0 and 1")


@dataclass
class RadarReviewQueueItem:
    candidate_id: str
    candidate: RadarCandidate
    summary: RadarSummaryForReview
    classification: RadarClassificationResult

    def __post_init__(self) -> None:
        self.candidate_id = _required_text(self.candidate_id, "candidate_id")


@dataclass
class RadarReviewDecision:
    candidate_id: str
    review_status: str
    reviewed_by: int | None = None
    admin_note: str | None = None

    def __post_init__(self) -> None:
        self.candidate_id = _required_text(self.candidate_id, "candidate_id")
        self.review_status = validate_review_status(self.review_status)
        if self.review_status == "pending":
            raise ValueError("review decision cannot be pending")
        if self.reviewed_by is not None:
            self.reviewed_by = int(self.reviewed_by)
        self.admin_note = (self.admin_note or "").strip() or None


@dataclass
class ReviewQueueReport:
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    needs_edit: int = 0
    errors: list[str] = field(default_factory=list)
