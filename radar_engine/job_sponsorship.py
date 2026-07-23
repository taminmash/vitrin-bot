from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping


SPONSORSHIP_YES = "YES"
SPONSORSHIP_NO = "NO"
SPONSORSHIP_UNKNOWN = "UNKNOWN"
SPONSORSHIP_VALUES = (SPONSORSHIP_YES, SPONSORSHIP_NO, SPONSORSHIP_UNKNOWN)
SPONSORSHIP_EVIDENCE_VERIFIED_KEY = "visa_sponsorship_evidence_verified"
MIN_EVIDENCE_LENGTH = 20
MIN_EVIDENCE_TOKENS = 4

EXPLICIT_SUPPORT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:work )?visa sponsorship\b",
        r"\bsponsor(?:s|ed|ing)?\b.{0,50}\b(?:work )?visa\b",
        r"\b(?:work )?visa\b.{0,50}\bsponsor(?:ship|s|ed|ing)?\b",
        r"\b(?:provide|provides|provided|offer|offers|offered)\b.{0,50}"
        r"\b(?:work visa|visa|work permit)\b.{0,30}\b(?:sponsorship|support|assistance)\b",
        r"\b(?:support|assistance)\b.{0,40}\b(?:work visa|work permit)\b",
        r"\bpatrocin(?:io|amos|a|ara|ará)\b.{0,50}\b(?:visado|visa|permiso de trabajo)\b",
        r"\b(?:visado|visa|permiso de trabajo)\b.{0,50}\bpatrocin(?:io|amos|a|ara|ará)\b",
        r"\b(?:apoyo|asistencia)\b.{0,50}\b(?:visado|visa|permiso de trabajo)\b",
        r"\b(?:ofrecemos|ofrece|proporcionamos|proporciona|brindamos|brinda)\b.{0,50}"
        r"\b(?:apoyo|asistencia|patrocinio)\b.{0,50}\b(?:visado|visa|permiso de trabajo)\b",
    )
)

EXPLICIT_DENIAL_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:do|does|did|will|can)\s+not\b.{0,30}\b(?:offer|provide|sponsor|support)\b"
        r".{0,50}\b(?:visa|sponsorship|work permit)\b",
        r"\b(?:visa sponsorship|work visa support|work permit support|sponsorship)\b"
        r".{0,35}\b(?:not available|unavailable|not provided|not offered|not supported)\b",
        r"\bno\b.{0,20}\b(?:visa sponsorship|work visa support|work permit support|sponsorship)\b",
        r"\b(?:unable|not able)\s+to\s+(?:offer|provide|sponsor|support)\b"
        r".{0,50}\b(?:visa|work permit|sponsorship)\b",
        r"\bsponsorship\b.{0,30}\bwill\s+not\s+be\s+(?:provided|offered|available)\b",
        r"\bno\s+(?:ofrecemos|ofrece|se ofrece|proporcionamos|proporciona|brindamos|brinda)\b"
        r".{0,50}\b(?:patrocinio|apoyo|asistencia)\b.{0,50}"
        r"\b(?:visado|visa|permiso de trabajo)\b",
        r"\b(?:patrocinio (?:de|del) (?:visado|visa)|"
        r"(?:apoyo|asistencia) (?:para|con|al) (?:el )?(?:visado|visa|permiso de trabajo))\b"
        r".{0,35}\bno (?:esta|está) disponible\b",
        r"\bno hay\b.{0,30}\b(?:patrocinio|apoyo|asistencia)\b.{0,40}"
        r"\b(?:visado|visa|permiso de trabajo)\b",
    )
)


def normalize_sponsorship_value(value) -> str:
    normalized = str(value or SPONSORSHIP_UNKNOWN).strip().upper()
    return normalized if normalized in SPONSORSHIP_VALUES else SPONSORSHIP_UNKNOWN


def normalize_evidence_text(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def has_explicit_support_statement(evidence) -> bool:
    normalized = normalize_evidence_text(evidence)
    tokens = re.findall(r"\b\w+\b", normalized, flags=re.UNICODE)
    if len(normalized) < MIN_EVIDENCE_LENGTH or len(tokens) < MIN_EVIDENCE_TOKENS:
        return False
    # Only denials grammatically tied to sponsorship/support terms reject the
    # excerpt. Unrelated negation elsewhere remains eligible for positive checks.
    if any(pattern.search(normalized) for pattern in EXPLICIT_DENIAL_PATTERNS):
        return False
    return any(pattern.search(normalized) for pattern in EXPLICIT_SUPPORT_PATTERNS)


def evidence_matches_original(evidence, title, body) -> bool:
    needle = normalize_evidence_text(evidence)
    if not has_explicit_support_statement(needle):
        return False
    title_source = normalize_evidence_text(title)
    body_source = normalize_evidence_text(body)
    return needle in title_source or needle in body_source


def apply_sponsorship_verification(structured_data: dict, *, title, body) -> dict:
    structured = dict(structured_data)
    sponsorship = normalize_sponsorship_value(structured.get("visa_sponsorship"))
    evidence = str(structured.get("visa_sponsorship_evidence") or "").strip() or None
    verified = (
        sponsorship == SPONSORSHIP_YES
        and evidence is not None
        and evidence_matches_original(evidence, title, body)
    )
    structured["visa_sponsorship"] = sponsorship
    structured["visa_sponsorship_evidence"] = evidence
    structured[SPONSORSHIP_EVIDENCE_VERIFIED_KEY] = verified
    return structured


def has_verified_sponsorship(structured_data) -> bool:
    if not isinstance(structured_data, Mapping):
        return False
    return (
        normalize_sponsorship_value(structured_data.get("visa_sponsorship")) == SPONSORSHIP_YES
        and bool(str(structured_data.get("visa_sponsorship_evidence") or "").strip())
        and structured_data.get(SPONSORSHIP_EVIDENCE_VERIFIED_KEY) is True
    )
