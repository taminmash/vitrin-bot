from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from radar_engine.models import RawRadarItem


TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    stripped = url.strip()
    if not stripped:
        return None
    parsed = urlsplit(stripped)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key in TRACKING_QUERY_KEYS or lower_key.startswith(TRACKING_QUERY_PREFIXES):
            continue
        query_pairs.append((key, value))
    query = urlencode(query_pairs, doseq=True)
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized or None


def _datetime_value(value):
    return value.isoformat() if value else None


def build_content_hash(item: RawRadarItem) -> str:
    payload = {
        "source_key": item.source_key,
        "external_id": item.external_id,
        "canonical_url": normalize_url(item.canonical_url or item.source_url),
        "original_title": item.original_title.strip(),
        "original_text": item.original_text.strip(),
        "original_language": item.original_language.strip(),
        "published_at": _datetime_value(item.published_at),
        "valid_from": _datetime_value(item.valid_from),
        "valid_until": _datetime_value(item.valid_until),
        "raw_category": item.raw_category,
        "raw_location": item.raw_location,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_key(parts: dict) -> str:
    encoded = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_deduplication_key(item: RawRadarItem) -> str:
    if item.external_id:
        return f"{item.source_key}:external:{item.external_id.strip()}"
    canonical_url = normalize_url(item.canonical_url or item.source_url)
    if canonical_url:
        return f"{item.source_key}:url:{canonical_url}"
    return f"{item.source_key}:hash:{_hash_key({'title': item.original_title, 'text': item.original_text})}"
