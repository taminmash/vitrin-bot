from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _clean_required(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


@dataclass
class RawRadarItem:
    source_key: str
    external_id: str
    source_name: str
    source_url: str
    original_title: str
    original_text: str
    original_language: str
    published_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    raw_category: str | None
    raw_location: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    canonical_url: str | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        self.source_key = _clean_required(self.source_key, "source_key")
        self.external_id = (self.external_id or "").strip()
        self.source_name = _clean_required(self.source_name, "source_name")
        self.source_url = _clean_required(self.source_url, "source_url")
        self.original_title = _clean_required(self.original_title, "original_title")
        self.original_text = _clean_required(self.original_text, "original_text")
        self.original_language = _clean_required(self.original_language, "original_language")
        self.raw_category = _clean_optional(self.raw_category)
        self.raw_location = _clean_optional(self.raw_location)
        self.canonical_url = _clean_optional(self.canonical_url)
        self.content_hash = _clean_optional(self.content_hash)
        if self.metadata is None:
            self.metadata = {}
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
