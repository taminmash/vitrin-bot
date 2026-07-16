from __future__ import annotations


TELEGRAM_CALLBACK_DATA_LIMIT = 64
REVIEW_CALLBACK_PREFIX = "admin_radar:r"


def _callback_byte_length(callback_data: str) -> int:
    return len(callback_data.encode("utf-8"))


def review_callback_data(operation: str, candidate_id) -> str:
    candidate_id = str(candidate_id)
    callback_data = f"{REVIEW_CALLBACK_PREFIX}:{operation}:{candidate_id}"
    if _callback_byte_length(callback_data) > TELEGRAM_CALLBACK_DATA_LIMIT:
        raise ValueError("Radar review callback_data exceeds Telegram limit")
    return callback_data


def review_callback_byte_length(operation: str, candidate_id) -> int:
    return _callback_byte_length(f"{REVIEW_CALLBACK_PREFIX}:{operation}:{candidate_id}")
