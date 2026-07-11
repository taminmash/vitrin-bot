from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _trim_required(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def _trim_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _trim_text(value: str | None) -> str:
    return (value or "").strip()


@dataclass
class StoredRawRadarItem:
    id: str
    source_key: str
    external_id: str | None
    source_name: str
    source_url: str
    canonical_url: str | None
    original_title: str
    original_text: str
    original_language: str
    published_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    raw_category: str | None
    raw_location: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    ingestion_status: str = "raw"
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.id = _trim_required(str(self.id), "id")
        self.source_key = _trim_required(self.source_key, "source_key")
        self.external_id = _trim_optional(self.external_id)
        self.source_name = _trim_required(self.source_name, "source_name")
        self.source_url = _trim_required(self.source_url, "source_url")
        self.canonical_url = _trim_optional(self.canonical_url)
        self.original_title = _trim_text(self.original_title)
        self.original_text = _trim_text(self.original_text)
        self.original_language = _trim_required(self.original_language, "original_language")
        self.raw_category = _trim_optional(self.raw_category)
        self.raw_location = _trim_optional(self.raw_location)
        self.ingestion_status = _trim_required(self.ingestion_status, "ingestion_status")
        if self.metadata is None:
            self.metadata = {}
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")


@dataclass
class SourceInfo:
    source_key: str
    name: str
    category: str | None
    source_type: str
    trust_level: int
    country: str = "Spain"
    city: str | None = None

    def __post_init__(self) -> None:
        self.source_key = _trim_required(self.source_key, "source_key")
        self.name = _trim_required(self.name, "name")
        self.category = _trim_optional(self.category)
        self.source_type = _trim_required(self.source_type, "source_type").lower()
        self.country = _trim_required(self.country or "Spain", "country")
        self.city = _trim_optional(self.city)
        self.trust_level = int(self.trust_level)
        if not 1 <= self.trust_level <= 5:
            raise ValueError("trust_level must be between 1 and 5")


@dataclass
class RadarCandidate:
    raw_item_id: str
    source_key: str
    source_name: str
    external_id: str | None
    title: str
    body: str
    language: str
    source_url: str
    canonical_url: str | None
    published_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    source_category: str | None
    source_location: str | None
    source_type: str
    trust_level: int
    metadata: dict[str, Any] = field(default_factory=dict)
    country: str = "Spain"
    candidate_status: str = "pending_ai"

    def __post_init__(self) -> None:
        self.raw_item_id = _trim_required(str(self.raw_item_id), "raw_item_id")
        self.source_key = _trim_required(self.source_key, "source_key")
        self.source_name = _trim_required(self.source_name, "source_name")
        self.external_id = _trim_optional(self.external_id)
        self.title = _trim_text(self.title)
        self.body = _trim_text(self.body)
        self.language = _trim_required(self.language, "language")
        self.source_url = _trim_required(self.source_url, "source_url")
        self.canonical_url = _trim_optional(self.canonical_url)
        self.source_category = _trim_optional(self.source_category)
        self.source_location = _trim_optional(self.source_location)
        self.country = _trim_required(self.country or "Spain", "country")
        self.source_type = _trim_required(self.source_type, "source_type").lower()
        self.candidate_status = _trim_required(self.candidate_status, "candidate_status")
        self.trust_level = int(self.trust_level)
        if not 1 <= self.trust_level <= 5:
            raise ValueError("trust_level must be between 1 and 5")
        if self.metadata is None:
            self.metadata = {}
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
