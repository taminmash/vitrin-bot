from __future__ import annotations

from uuid import uuid4

from radar_engine.publication.models import (
    EligiblePublicationItem,
    PublicationAttempt,
    PublicationClaim,
    PublicationResult,
    TelegramPublicationResponse,
)


DEFAULT_CLAIM_TTL_SECONDS = 600


def _row_to_item(row) -> EligiblePublicationItem:
    return EligiblePublicationItem(dict(row))


def _row_to_attempt(row) -> PublicationAttempt:
    data = dict(row)
    return PublicationAttempt(
        id=data.get("id"),
        radar_item_id=data["radar_item_id"],
        attempt_token=data["attempt_token"],
        attempt_status=data["attempt_status"],
        telegram_message_id=data.get("telegram_message_id"),
        channel_id=data.get("channel_id"),
        channel_post_url=data.get("channel_post_url"),
        last_error=data.get("last_error"),
    )


def _eligible_where(include_failed: bool = False) -> str:
    status_clause = "COALESCE(channel_status, 'not_sent') IN ('not_sent', 'failed')" if include_failed else "COALESCE(channel_status, 'not_sent') = 'not_sent'"
    return f"""
        COALESCE(content_status, 'draft') = 'ready'
        AND {status_clause}
        AND COALESCE(is_published, false) = false
        AND channel_message_id IS NULL
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        AND (end_date IS NULL OR end_date > CURRENT_TIMESTAMP)
        AND NOT EXISTS (
            SELECT 1
            FROM radar_publications pubs
            WHERE pubs.radar_item_id = radar_items.id
              AND pubs.publication_status = 'published'
        )
    """


def load_ready_publication_items(
    limit: int = 20,
    radar_item_id: str | None = None,
    include_failed: bool = False,
) -> list[EligiblePublicationItem]:
    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), 20))
    with db_cursor(dict_cursor=True) as (_, cur):
        if radar_item_id:
            cur.execute(
                f"""
                SELECT *
                FROM radar_items
                WHERE id = %s
                  AND {_eligible_where(include_failed)}
                LIMIT 1
                """,
                (radar_item_id,),
            )
        else:
            cur.execute(
                f"""
                SELECT *
                FROM radar_items
                WHERE {_eligible_where(include_failed)}
                ORDER BY COALESCE(ai_priority, priority_score, 0) DESC,
                         updated_at ASC,
                         created_at ASC
                LIMIT %s
                """,
                (safe_limit,),
            )
        return [_row_to_item(row) for row in cur.fetchall()]


def get_existing_successful_publication(radar_item_id: str) -> dict | None:
    from database.db import db_cursor, row_to_dict

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM radar_publications
            WHERE radar_item_id = %s
              AND publication_status = 'published'
            LIMIT 1
            """,
            (radar_item_id,),
        )
        return row_to_dict(cur.fetchone())


def get_radar_item_channel_message(radar_item_id: str) -> dict | None:
    from database.db import db_cursor, row_to_dict

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT id, channel_message_id, channel_status, content_status
            FROM radar_items
            WHERE id = %s
              AND channel_message_id IS NOT NULL
            LIMIT 1
            """,
            (radar_item_id,),
        )
        return row_to_dict(cur.fetchone())


def claim_publication_attempt(
    radar_item_id: str,
    claimed_by: int | None = None,
    ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
) -> PublicationClaim:
    from database.db import db_cursor

    attempt_token = str(uuid4())
    safe_ttl = max(60, min(int(ttl_seconds), 3600))
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_publication_attempts
            SET attempt_status = 'failed',
                last_error = COALESCE(last_error, 'sending claim expired before completion'),
                updated_at = CURRENT_TIMESTAMP
            WHERE radar_item_id = %s
              AND attempt_status = 'sending'
              AND expires_at <= CURRENT_TIMESTAMP
            """,
            (radar_item_id,),
        )
        cur.execute(
            """
            SELECT *
            FROM radar_publication_attempts
            WHERE radar_item_id = %s
              AND attempt_status IN ('sent_unpersisted', 'ambiguous')
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (radar_item_id,),
        )
        reconcilable = cur.fetchone()
        if reconcilable:
            return PublicationClaim("reconciliation_required", _row_to_attempt(reconcilable))
        cur.execute(
            """
            INSERT INTO radar_publication_attempts (
                radar_item_id, attempt_token, attempt_status, claimed_by,
                claimed_at, expires_at
            )
            VALUES (%s, %s, 'sending', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'))
            ON CONFLICT (radar_item_id) WHERE attempt_status = 'sending'
            DO NOTHING
            RETURNING *
            """,
            (radar_item_id, attempt_token, claimed_by, safe_ttl),
        )
        inserted = cur.fetchone()
        if inserted:
            return PublicationClaim("claimed", _row_to_attempt(inserted))
        cur.execute(
            """
            SELECT *
            FROM radar_publication_attempts
            WHERE radar_item_id = %s
              AND attempt_status = 'sending'
              AND expires_at > CURRENT_TIMESTAMP
            ORDER BY claimed_at DESC
            LIMIT 1
            """,
            (radar_item_id,),
        )
        active = cur.fetchone()
        if active:
            return PublicationClaim("publication_in_progress", _row_to_attempt(active))
        return PublicationClaim("publication_in_progress")


def mark_attempt_sent(attempt: PublicationAttempt, response: TelegramPublicationResponse) -> PublicationAttempt:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_publication_attempts
            SET attempt_status = 'sent_unpersisted',
                telegram_message_id = %s,
                channel_id = %s,
                channel_post_url = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE radar_item_id = %s
              AND attempt_token = %s
              AND attempt_status = 'sending'
            RETURNING *
            """,
            (
                response.telegram_message_id,
                response.channel_id,
                response.channel_post_url,
                attempt.radar_item_id,
                attempt.attempt_token,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("publication attempt is no longer sendable")
        return _row_to_attempt(row)


def mark_attempt_completed(attempt: PublicationAttempt) -> None:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_publication_attempts
            SET attempt_status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE radar_item_id = %s
              AND attempt_token = %s
              AND attempt_status IN ('sending', 'sent_unpersisted', 'ambiguous')
            """,
            (attempt.radar_item_id, attempt.attempt_token),
        )


def mark_attempt_failed(attempt: PublicationAttempt, error_text: str) -> None:
    from database.db import db_cursor

    safe_error = (error_text or "publication failed")[:1000]
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_publication_attempts
            SET attempt_status = 'failed',
                last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE radar_item_id = %s
              AND attempt_token = %s
              AND attempt_status = 'sending'
            """,
            (safe_error, attempt.radar_item_id, attempt.attempt_token),
        )


def mark_attempt_ambiguous(attempt: PublicationAttempt, error_text: str) -> None:
    from database.db import db_cursor

    safe_error = (error_text or "publication outcome ambiguous")[:1000]
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_publication_attempts
            SET attempt_status = 'ambiguous',
                last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE radar_item_id = %s
              AND attempt_token = %s
              AND attempt_status = 'sending'
            """,
            (safe_error, attempt.radar_item_id, attempt.attempt_token),
        )


def record_publication_success(
    radar_item_id: str,
    response: TelegramPublicationResponse,
    published_by: int | None = None,
) -> PublicationResult:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT id FROM radar_items WHERE id = %s FOR UPDATE", (radar_item_id,))
        if not cur.fetchone():
            raise ValueError("radar item not found")
        cur.execute(
            """
            INSERT INTO radar_publications (
                radar_item_id, channel_id, telegram_message_id, channel_post_url,
                publication_status, attempt_count, published_by, last_error
            )
            VALUES (%s, %s, %s, %s, 'published', 1, %s, NULL)
            ON CONFLICT (radar_item_id) WHERE publication_status = 'published'
            DO NOTHING
            RETURNING id
            """,
            (
                radar_item_id,
                response.channel_id,
                response.telegram_message_id,
                response.channel_post_url,
                published_by,
            ),
        )
        inserted = cur.fetchone()
        if not inserted:
            return PublicationResult(radar_item_id, "already_published")
        cur.execute(
            """
            UPDATE radar_items
            SET content_status = 'published',
                channel_status = 'published',
                is_published = true,
                published_at = COALESCE(published_at, CURRENT_TIMESTAMP),
                channel_published_at = CURRENT_TIMESTAMP,
                channel_message_id = %s,
                channel_post_url = %s,
                last_publish_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id
            """,
            (response.telegram_message_id, response.channel_post_url, radar_item_id),
        )
        cur.fetchone()
        return PublicationResult(
            radar_item_id,
            "published",
            telegram_message_id=response.telegram_message_id,
            channel_id=response.channel_id,
            channel_post_url=response.channel_post_url,
        )


def record_publication_failure(
    radar_item_id: str,
    channel_id: str,
    error_text: str,
    published_by: int | None = None,
) -> PublicationResult:
    from database.db import db_cursor

    safe_error = (error_text or "publication failed")[:1000]
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            INSERT INTO radar_publications (
                radar_item_id, channel_id, telegram_message_id, publication_status,
                attempt_count, published_by, last_error
            )
            VALUES (%s, %s, 0, 'failed', 1, %s, %s)
            """,
            (radar_item_id, str(channel_id), published_by, safe_error),
        )
        cur.execute(
            """
            UPDATE radar_items
            SET channel_status = 'failed',
                last_publish_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (safe_error, radar_item_id),
        )
    return PublicationResult(radar_item_id, "telegram_failed", channel_id=str(channel_id), error=safe_error)


def reconcile_publication(
    radar_item_id: str,
    telegram_message_id: int,
    channel_id: str,
    channel_post_url: str | None = None,
    published_by: int | None = None,
) -> PublicationResult:
    if get_existing_successful_publication(radar_item_id):
        return PublicationResult(radar_item_id, "already_published")
    response = TelegramPublicationResponse(
        channel_id=str(channel_id),
        telegram_message_id=int(telegram_message_id),
        channel_post_url=channel_post_url,
    )
    result = record_publication_success(radar_item_id, response, published_by=published_by)
    if result.published:
        complete_reconcilable_attempt(radar_item_id, response)
    return result


def complete_reconcilable_attempt(radar_item_id: str, response: TelegramPublicationResponse) -> None:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_publication_attempts
            SET attempt_status = 'completed',
                telegram_message_id = COALESCE(telegram_message_id, %s),
                channel_id = COALESCE(channel_id, %s),
                channel_post_url = COALESCE(channel_post_url, %s),
                updated_at = CURRENT_TIMESTAMP
            WHERE radar_item_id = %s
              AND attempt_status IN ('sent_unpersisted', 'ambiguous')
            """,
            (response.telegram_message_id, response.channel_id, response.channel_post_url, radar_item_id),
        )
