from __future__ import annotations

from dataclasses import dataclass


def _required_text(value, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


@dataclass
class AITaskResult:
    headline: str
    short_summary: str
    why_it_matters: str
    confidence: float
    model_name: str
    prompt_version: str
    processing_time_ms: int

    def __post_init__(self) -> None:
        self.headline = _required_text(self.headline, "headline")
        self.short_summary = _required_text(self.short_summary, "short_summary")
        self.why_it_matters = _required_text(self.why_it_matters, "why_it_matters")
        self.model_name = _required_text(self.model_name, "model_name")
        self.prompt_version = _required_text(self.prompt_version, "prompt_version")
        self.confidence = float(self.confidence)
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        self.processing_time_ms = int(self.processing_time_ms)
        if self.processing_time_ms < 0:
            raise ValueError("processing_time_ms must not be negative")


@dataclass
class StoredAICandidate:
    candidate_id: str
    candidate: object
