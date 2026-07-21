from __future__ import annotations


FULL_TEXT_FA_KEY = "full_text_fa"
PERSIAN_FULL_DETAIL_HEADING = "📄 توضیحات کامل فارسی"
PERSIAN_TRANSLATION_PENDING = "ترجمه فارسی این محتوا هنوز آماده نشده است."
TELEGRAM_SAFE_TEXT_LIMIT = 3800


def _clean(value) -> str:
    return ("" if value is None else str(value)).strip()


def is_boe_content(item) -> bool:
    if not isinstance(item, dict):
        return False
    source_key = _clean(item.get("source_key")).casefold()
    source_name = _clean(item.get("source_name")).casefold()
    source_url = _clean(item.get("source_url")).casefold()
    return source_key == "boe" or source_name == "boe" or "boe.es/" in source_url


def persian_full_text(item) -> str:
    if not isinstance(item, dict):
        return ""
    structured = item.get("structured_data")
    if not isinstance(structured, dict):
        structured = {}
    return _clean(structured.get(FULL_TEXT_FA_KEY))


def persian_detail_text(item) -> str:
    return persian_full_text(item) or PERSIAN_TRANSLATION_PENDING


def split_telegram_text(text, max_length: int = TELEGRAM_SAFE_TEXT_LIMIT) -> list[str]:
    """Split ordered Telegram text at paragraph/line/word boundaries."""
    cleaned = _clean(text)
    if not cleaned:
        return [""]
    limit = max(1, int(max_length))
    if len(cleaned) <= limit:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    while len(remaining) > limit:
        window = remaining[: limit + 1]
        split_at = window.rfind("\n\n", 0, limit + 1)
        separator_length = 2
        if split_at <= 0:
            split_at = window.rfind("\n", 0, limit + 1)
            separator_length = 1
        if split_at <= 0:
            split_at = window.rfind(" ", 0, limit + 1)
            separator_length = 1
        if split_at <= 0:
            split_at = limit
            separator_length = 0
        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:limit]
            split_at = len(chunk)
            separator_length = 0
        chunks.append(chunk)
        remaining = remaining[split_at + separator_length :].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
