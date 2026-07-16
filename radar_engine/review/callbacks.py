from __future__ import annotations

from hashlib import blake2s


TELEGRAM_CALLBACK_DATA_LIMIT = 64
REVIEW_CALLBACK_PREFIX = "admin_radar:r"
REVIEW_CALLBACK_CANDIDATES: dict[str, str] = {}


def review_candidate_token(candidate_id) -> str:
    candidate_id = str(candidate_id)
    token = blake2s(candidate_id.encode("utf-8"), digest_size=8).hexdigest()
    REVIEW_CALLBACK_CANDIDATES[token] = candidate_id
    return token


def review_callback_data(operation: str, candidate_id) -> str:
    token = review_candidate_token(candidate_id)
    callback_data = f"{REVIEW_CALLBACK_PREFIX}:{operation}:{token}"
    if len(callback_data.encode("utf-8")) > TELEGRAM_CALLBACK_DATA_LIMIT:
        raise ValueError("Radar review callback_data exceeds Telegram limit")
    return callback_data


def resolve_review_candidate_token(token: str) -> str | None:
    return REVIEW_CALLBACK_CANDIDATES.get(str(token))
