from __future__ import annotations

import re
import unicodedata


UNKNOWN_JOB_TITLE = "عنوان شغل مشخص نشده است"
MIN_AI_TITLE_CONFIDENCE = 0.85

_GENERIC_TITLES = {
    "استخدام برای یک موقعیت شغلی",
    "یک موقعیت شغلی",
    "موقعیت شغلی",
    "فرصت شغلی",
    "فرصت استخدام",
    "استخدام",
    "una plaza",
    "puesto",
    "un puesto",
    "oferta de empleo",
    "job opportunity",
    "unknown",
}
_OFFICIAL_BOILERPLATE = re.compile(r"^(resoluci[oó]n|convocatoria|anuncio|proceso selectivo)\b", re.IGNORECASE)
_AI_FORBIDDEN_PHRASES = ("فرصت شغلی", "موقعیت شغلی", "فرصت استخدام", "استخدام")


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def is_meaningful_job_title(value, *, source_title: bool = False) -> bool:
    title = _clean(value)
    if not title or title.casefold() in _GENERIC_TITLES:
        return False
    if source_title and _OFFICIAL_BOILERPLATE.search(title):
        return False
    return any(character.isalpha() for character in title)


def valid_ai_job_title(value, confidence) -> str | None:
    title = _clean(value)
    try:
        score = float(confidence)
    except (TypeError, ValueError):
        return None
    if score < MIN_AI_TITLE_CONFIDENCE or not is_meaningful_job_title(title):
        return None
    if len(title.split()) > 6 or any(phrase in title for phrase in _AI_FORBIDDEN_PHRASES):
        return None
    if not any("\u0600" <= character <= "\u06ff" for character in title):
        return None
    for character in title:
        if character.isspace() or character == "\u200c":
            continue
        if not unicodedata.category(character).startswith(("L", "M")):
            return None
    return title


def displayed_job_title(
    normalized_title,
    structured_metadata=None,
    ai_title=None,
    ai_confidence=None,
) -> str:
    existing = existing_job_title(normalized_title, structured_metadata)
    if existing:
        return existing
    return valid_ai_job_title(ai_title, ai_confidence) or UNKNOWN_JOB_TITLE


def existing_job_title(normalized_title, structured_metadata=None) -> str | None:
    if is_meaningful_job_title(normalized_title, source_title=True):
        return _clean(normalized_title)

    metadata = structured_metadata if isinstance(structured_metadata, dict) else {}
    for key in ("normalized_job_title", "job_title", "occupation", "profession"):
        value = metadata.get(key)
        if is_meaningful_job_title(value):
            return _clean(value)
    return None
