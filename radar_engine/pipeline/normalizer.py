from __future__ import annotations

import re

from radar_engine.pipeline.candidate import RadarCandidate, SourceInfo, StoredRawRadarItem


def normalize_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "\n".join(line.strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize_raw_item(raw_item: StoredRawRadarItem, source_info: SourceInfo) -> RadarCandidate:
    metadata = dict(raw_item.metadata or {})
    if source_info.category:
        metadata.setdefault("source_registry_category", source_info.category)
    if source_info.city:
        metadata.setdefault("source_registry_city", source_info.city)
    return RadarCandidate(
        raw_item_id=str(raw_item.id),
        source_key=raw_item.source_key,
        source_name=source_info.name or raw_item.source_name,
        external_id=raw_item.external_id,
        title=normalize_text(raw_item.original_title),
        body=normalize_text(raw_item.original_text),
        language=normalize_text(raw_item.original_language),
        source_url=raw_item.source_url,
        canonical_url=raw_item.canonical_url,
        published_at=raw_item.published_at,
        valid_from=raw_item.valid_from,
        valid_until=raw_item.valid_until,
        source_category=raw_item.raw_category,
        source_location=raw_item.raw_location,
        country=source_info.country or "Spain",
        source_type=source_info.source_type,
        trust_level=source_info.trust_level,
        candidate_status="pending_ai",
        metadata=metadata,
    )
