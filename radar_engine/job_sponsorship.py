from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping


SPONSORSHIP_YES = "YES"
SPONSORSHIP_NO = "NO"
SPONSORSHIP_UNKNOWN = "UNKNOWN"
SPONSORSHIP_VALUES = (SPONSORSHIP_YES, SPONSORSHIP_NO, SPONSORSHIP_UNKNOWN)
SPONSORSHIP_EVIDENCE_VERIFIED_KEY = "visa_sponsorship_evidence_verified"


def normalize_sponsorship_value(value) -> str:
    normalized = str(value or SPONSORSHIP_UNKNOWN).strip().upper()
    return normalized if normalized in SPONSORSHIP_VALUES else SPONSORSHIP_UNKNOWN


def normalize_evidence_text(value) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def evidence_matches_original(evidence, title, body) -> bool:
    needle = normalize_evidence_text(evidence)
    if not needle:
        return False
    source = normalize_evidence_text(" ".join(part for part in (title, body) if part))
    return needle in source


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
