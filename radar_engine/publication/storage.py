from __future__ import annotations

from radar_engine.publication.models import EligiblePublicationItem, PublicationResult, TelegramPublicationResponse


def _row_to_item(row) -> EligiblePublicationItem:
    return EligiblePublicationItem(dict(row))


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
    return record_publication_success(radar_item_id, response, published_by=published_by)
