from __future__ import annotations

from radar_engine.promotion.models import ApprovedPromotionSource, MappedRadarItemPayload, RADAR_READY_STATUS
from radar_engine.taxonomy import RADAR_CATEGORY_VALUES, RADAR_URGENCY_VALUES
from radar_engine.job_expiration import parse_source_datetime


def _clean(value) -> str:
    return ("" if value is None else str(value)).strip()


def _dedupe(values: list[str] | tuple[str, ...] | None) -> list[str]:
    cleaned = []
    seen = set()
    for value in values or []:
        item = _clean(value)
        if item and item not in seen:
            cleaned.append(item)
            seen.add(item)
    return cleaned


def validate_mapped_payload(payload: MappedRadarItemPayload) -> list[dict[str, str]]:
    fields = payload.fields
    errors: list[dict[str, str]] = []
    required = {
        "title": "blank_title",
        "summary": "blank_summary",
        "source_url": "blank_source_url",
        "source_name": "blank_source_name",
    }
    for field, code in required.items():
        if not _clean(fields.get(field)):
            errors.append({"field": field, "code": code, "message": f"{field} is required"})
    if payload.content_status != RADAR_READY_STATUS:
        errors.append({"field": "content_status", "code": "invalid_status", "message": "status must be ready"})
    if fields.get("type") not in RADAR_CATEGORY_VALUES:
        errors.append({"field": "type", "code": "invalid_category", "message": "type is not a Radar category"})
    if fields.get("category") not in RADAR_CATEGORY_VALUES:
        errors.append({"field": "category", "code": "invalid_category", "message": "category is not a Radar category"})
    if fields.get("urgency") not in RADAR_URGENCY_VALUES:
        errors.append({"field": "urgency", "code": "invalid_urgency", "message": "urgency is not supported"})
    return errors


def map_approved_source_to_radar_item(source: ApprovedPromotionSource) -> MappedRadarItemPayload:
    candidate = source.candidate
    summary = source.summary
    classification = source.classification
    category_tags = _dedupe(classification.category_tags or [classification.primary_category])
    if classification.primary_category not in category_tags:
        category_tags.insert(0, classification.primary_category)
    audience_tags = _dedupe(classification.audience_tags)
    cities = _dedupe(classification.cities)
    city = cities[0] if cities else None
    metadata = candidate.metadata or {}
    structured = dict(summary.structured_data) if isinstance(summary.structured_data, dict) else {}
    expires_at = candidate.valid_until
    if classification.primary_category == "job":
        structured.setdefault("publication_date", candidate.published_at.isoformat() if candidate.published_at else None)
        structured.setdefault("deadline_unknown", not bool(structured.get("deadline") or candidate.valid_until))
        structured.setdefault("stale_review", bool(metadata.get("stale_review")))
        expires_at = expires_at or parse_source_datetime(structured.get("deadline"), end_of_day=True)
    fields = {
        "title": _clean(structured.get("job_title")) or _clean(summary.headline),
        "summary": _clean(summary.summary),
        "body": _clean(candidate.body),
        "type": classification.primary_category,
        "category": classification.primary_category,
        "category_tags": category_tags,
        "city": _clean(structured.get("city")) or city,
        "province": _clean(structured.get("region")) or city,
        "country": candidate.country or "Spain",
        "start_date": candidate.valid_from or candidate.published_at,
        "end_date": candidate.valid_until,
        "source_url": _clean(candidate.source_url),
        "source_name": _clean(candidate.source_name),
        "urgency": classification.urgency,
        "priority_score": int(classification.priority_score),
        "audience_tags": audience_tags,
        "is_verified": True,
        "expires_at": expires_at,
        "ai_summary": _clean(summary.summary),
        "ai_reason": _clean(summary.why_it_matters),
        "ai_tags": audience_tags,
        "ai_priority": int(classification.priority_score),
        "structured_data": structured,
        "original_text": _clean(candidate.body),
        "original_language": candidate.language,
    }
    if classification.geographic_scope == "national" and not (structured.get("city") or structured.get("region")):
        fields["city"] = None
        fields["province"] = None
    if metadata:
        fields["body"] = fields["body"] or _clean(metadata.get("body"))
    return MappedRadarItemPayload(fields=fields, content_status=RADAR_READY_STATUS)
