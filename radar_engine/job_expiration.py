from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import os
import re
from zoneinfo import ZoneInfo


MADRID_TZ = ZoneInfo("Europe/Madrid")
EXPIRED_PUBLICATION_MESSAGE = "⛔ این آگهی منقضی شده است و امکان انتشار آن به‌عنوان فرصت فعال وجود ندارد."
EXPIRED_DETAIL_MESSAGE = (
    "⛔ این آگهی منقضی شده است\n\n"
    "مهلت ارسال درخواست به پایان رسیده و امکان اقدام از طریق این آگهی تأیید نمی‌شود."
)
STALE_REVIEW_MESSAGE = "⚠️ نیازمند بررسی اعتبار"
UNKNOWN_DEADLINE_MESSAGE = "ذکر نشده"

_CLOSED_STATUSES = {
    "closed", "expired", "no longer accepting applications", "oferta finalizada",
    "convocatoria cerrada", "plazo finalizado", "plazo cerrado", "proceso cerrado",
}


def madrid_now() -> datetime:
    return datetime.now(MADRID_TZ)


def stale_review_days() -> int:
    try:
        return max(1, min(365, int(os.getenv("RADAR_JOB_STALE_REVIEW_DAYS", "30"))))
    except ValueError:
        return 30


def expired_channel_edit_enabled() -> bool:
    return os.getenv("RADAR_EXPIRED_CHANNEL_EDIT_ENABLED", "false").strip().casefold() in {"1", "true", "yes", "on"}


def _mapping(value) -> dict:
    return value if isinstance(value, dict) else {}


def parse_source_datetime(value, *, end_of_day: bool = False) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.max if end_of_day else time.min)
    else:
        text = str(value).strip()
        parsed = None
        for candidate in (text, text.replace("Z", "+00:00")):
            try:
                parsed = datetime.fromisoformat(candidate)
                break
            except ValueError:
                pass
        if parsed is None:
            for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    parsed = datetime.strptime(text, pattern)
                    break
                except ValueError:
                    pass
        if parsed is None:
            return None
        if len(text) == 10 and end_of_day:
            parsed = datetime.combine(parsed.date(), time.max)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=MADRID_TZ)
    return parsed.astimezone(MADRID_TZ)


def source_closed_status(item: dict) -> str | None:
    structured = _mapping(item.get("structured_data"))
    metadata = _mapping(item.get("metadata"))
    for value in (
        structured.get("source_status"), item.get("source_status"), metadata.get("source_status"),
    ):
        normalized = re.sub(r"\s+", " ", str(value or "").strip().casefold())
        if normalized in _CLOSED_STATUSES:
            return normalized
    return None


def publication_datetime(item: dict) -> tuple[datetime | None, str | None]:
    structured = _mapping(item.get("structured_data"))
    metadata = _mapping(item.get("metadata"))
    candidates = (
        (structured.get("source_published_at") or structured.get("publication_date"), "structured"),
        (item.get("published_at") or item.get("start_date"), "normalized"),
        (metadata.get("source_published_at") or metadata.get("publication_date"), "source_metadata"),
        (item.get("first_seen_at"), "first_seen_fallback"),
    )
    for value, provenance in candidates:
        parsed = parse_source_datetime(value)
        if parsed:
            return parsed, provenance
    return None, None


def deadline_datetime(item: dict) -> tuple[datetime | None, str | None]:
    structured = _mapping(item.get("structured_data"))
    metadata = _mapping(item.get("metadata"))
    candidates = (
        (structured.get("application_deadline") or structured.get("deadline"), "structured"),
        (metadata.get("application_deadline") or metadata.get("deadline"), "source_metadata"),
        (item.get("valid_until") or item.get("end_date") or item.get("expires_at"), "normalized"),
    )
    for value, provenance in candidates:
        parsed = parse_source_datetime(value, end_of_day=True)
        if parsed:
            return parsed, provenance
    return None, None


@dataclass(frozen=True)
class JobTemporalState:
    publication_date: datetime | None
    publication_provenance: str | None
    deadline: datetime | None
    deadline_provenance: str | None
    expired: bool
    expiration_reason: str | None
    deadline_unknown: bool
    stale: bool
    days_remaining: int | None


def job_temporal_state(item: dict, *, now: datetime | None = None, stale_days: int | None = None) -> JobTemporalState:
    now = now or madrid_now()
    now = now.replace(tzinfo=MADRID_TZ) if now.tzinfo is None else now.astimezone(MADRID_TZ)
    publication, publication_provenance = publication_datetime(item)
    deadline, deadline_provenance = deadline_datetime(item)
    closed = source_closed_status(item)
    expired = bool(closed or (deadline and deadline < now) or item.get("content_status") == "expired")
    reason = f"source_status:{closed}" if closed else ("deadline_passed" if deadline and deadline < now else None)
    if item.get("content_status") == "expired" and not reason:
        reason = "persisted_expired_status"
    deadline_unknown = deadline is None and not closed
    threshold = stale_review_days() if stale_days is None else max(1, int(stale_days))
    stale = bool(deadline_unknown and publication and publication < now - timedelta(days=threshold))
    days_remaining = None
    if deadline and not expired:
        days_remaining = (deadline.date() - now.date()).days
    return JobTemporalState(
        publication, publication_provenance, deadline, deadline_provenance,
        expired, reason, deadline_unknown, stale, days_remaining,
    )


def format_job_date(value: datetime | None) -> str | None:
    return value.astimezone(MADRID_TZ).strftime("%Y-%m-%d") if value else None


@dataclass(frozen=True)
class ExpirationRefreshReport:
    evaluated: int = 0
    expired: int = 0
    stale: int = 0
    unchanged: int = 0
    expired_items: tuple[dict, ...] = ()


def refresh_expired_jobs(limit: int = 200) -> ExpirationRefreshReport:
    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), 500))
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM radar_items
            WHERE COALESCE(type, category) = 'job'
              AND COALESCE(content_status, 'draft') <> 'expired'
            ORDER BY COALESCE(expires_at, end_date, created_at) ASC
            LIMIT %s
            """,
            (safe_limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        expired = stale = unchanged = 0
        expired_items = []
        for item in rows:
            state = job_temporal_state(item)
            if state.expired:
                cur.execute(
                    """
                    UPDATE radar_items
                    SET content_status = 'expired',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND COALESCE(content_status, 'draft') <> 'expired'
                    """,
                    (item["id"],),
                )
                expired += cur.rowcount
                if cur.rowcount:
                    expired_items.append({**item, "content_status": "expired"})
            elif state.stale:
                cur.execute(
                    """
                    UPDATE radar_items
                    SET structured_data = jsonb_set(
                            jsonb_set(COALESCE(structured_data, '{}'::jsonb), '{deadline_unknown}', 'true'::jsonb, true),
                            '{stale_review}', 'true'::jsonb, true
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND COALESCE(structured_data ->> 'stale_review', 'false') <> 'true'
                    """,
                    (item["id"],),
                )
                stale += cur.rowcount
                unchanged += 0 if cur.rowcount else 1
            else:
                unchanged += 1
    return ExpirationRefreshReport(len(rows), expired, stale, unchanged, tuple(expired_items))
