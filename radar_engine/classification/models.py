from __future__ import annotations

from dataclasses import dataclass, field

from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.taxonomy import (
    RADAR_AUDIENCE_VALUES,
    RADAR_CATEGORY_VALUES,
    RADAR_CITY_VALUES,
    RADAR_GEOGRAPHIC_SCOPE_VALUES,
    RADAR_URGENCY_VALUES,
)


def _required_text(value, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def _clean_list(values, field_name: str, allowed: tuple[str, ...]) -> list[str]:
    if values is None:
        values = []
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list")
    cleaned = []
    seen = set()
    for value in values:
        item = (value or "").strip()
        if not item:
            continue
        if item not in allowed:
            raise ValueError(f"{field_name} contains unknown value: {item}")
        if item not in seen:
            cleaned.append(item)
            seen.add(item)
    return cleaned


@dataclass
class ClassificationSource:
    candidate_id: str
    ai_result_id: str
    candidate: RadarCandidate
    ai_headline: str
    ai_summary: str
    ai_why_it_matters: str

    def __post_init__(self) -> None:
        self.candidate_id = _required_text(self.candidate_id, "candidate_id")
        self.ai_result_id = _required_text(self.ai_result_id, "ai_result_id")
        self.ai_headline = _required_text(self.ai_headline, "ai_headline")
        self.ai_summary = _required_text(self.ai_summary, "ai_summary")
        self.ai_why_it_matters = (self.ai_why_it_matters or "").strip()


@dataclass
class RadarClassificationResult:
    candidate_id: str
    primary_category: str
    category_tags: list[str] = field(default_factory=list)
    audience_tags: list[str] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)
    geographic_scope: str = "unknown"
    urgency: str = "low"
    priority_score: int = 0
    confidence: float = 0.0
    model_name: str = ""
    prompt_version: str = ""
    processing_time_ms: int = 0

    def __post_init__(self) -> None:
        self.candidate_id = _required_text(self.candidate_id, "candidate_id")
        self.primary_category = _required_text(self.primary_category, "primary_category")
        if self.primary_category not in RADAR_CATEGORY_VALUES:
            raise ValueError(f"primary_category contains unknown value: {self.primary_category}")
        self.category_tags = _clean_list(self.category_tags, "category_tags", RADAR_CATEGORY_VALUES)
        self.audience_tags = _clean_list(self.audience_tags, "audience_tags", RADAR_AUDIENCE_VALUES)
        self.cities = _clean_list(self.cities, "cities", RADAR_CITY_VALUES)
        self.geographic_scope = _required_text(self.geographic_scope, "geographic_scope")
        if self.geographic_scope not in RADAR_GEOGRAPHIC_SCOPE_VALUES:
            raise ValueError(f"geographic_scope contains unknown value: {self.geographic_scope}")
        self.urgency = _required_text(self.urgency, "urgency")
        if self.urgency not in RADAR_URGENCY_VALUES:
            raise ValueError(f"urgency contains unknown value: {self.urgency}")
        self.priority_score = int(self.priority_score)
        if not 0 <= self.priority_score <= 100:
            raise ValueError("priority_score must be between 0 and 100")
        self.confidence = float(self.confidence)
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        self.model_name = _required_text(self.model_name, "model_name")
        self.prompt_version = _required_text(self.prompt_version, "prompt_version")
        self.processing_time_ms = int(self.processing_time_ms)
        if self.processing_time_ms < 0:
            raise ValueError("processing_time_ms must not be negative")
