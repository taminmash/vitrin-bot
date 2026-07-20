from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from radar_engine.deduplication import build_content_hash, build_deduplication_key, normalize_url
from radar_engine.models import RawRadarItem


StoreStatus = Literal["inserted", "duplicate", "updated"]


@dataclass
class StoreResult:
    status: StoreStatus
    raw_item_id: UUID | str | None
    deduplication_key: str


def classify_existing_content(existing_content_hash: str | None, incoming_content_hash: str) -> StoreStatus:
    return "duplicate" if existing_content_hash == incoming_content_hash else "updated"


def _requeue_orphaned_job_raw(cur, raw_item_id, item: RawRadarItem) -> None:
    """Make a previously failed job raw visible again when it has no candidate."""
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    if str(metadata.get("content_type") or "").strip().casefold() != "job":
        return
    if metadata.get("is_expired") is True:
        return
    cur.execute(
        """
        UPDATE radar_raw_items AS raw
        SET ingestion_status = 'raw',
            updated_at = CURRENT_TIMESTAMP
        WHERE raw.id = %s
          AND raw.ingestion_status <> 'raw'
          AND lower(COALESCE(raw.metadata ->> 'content_type', %s)) = 'job'
          AND COALESCE(raw.metadata ->> 'is_expired', 'false') <> 'true'
          AND NOT EXISTS (
              SELECT 1
              FROM radar_candidates AS candidate
              WHERE candidate.raw_item_id = raw.id
          )
        """,
        (raw_item_id, "job"),
    )


def store_raw_item(item: RawRadarItem) -> StoreResult:
    from psycopg2.extras import Json

    from database.db import db_cursor

    content_hash = item.content_hash or build_content_hash(item)
    deduplication_key = build_deduplication_key(item)
    canonical_url = normalize_url(item.canonical_url or item.source_url)

    with db_cursor(dict_cursor=True) as (_, cur):
        fingerprint = item.metadata.get("job_fingerprint") if isinstance(item.metadata, dict) else None
        if fingerprint:
            cur.execute(
                """
                SELECT id, deduplication_key
                FROM radar_raw_items
                WHERE source_key <> %s
                  AND metadata ->> 'job_fingerprint' = %s
                ORDER BY first_seen_at ASC
                LIMIT 1
                """,
                (item.source_key, fingerprint),
            )
            cross_source = cur.fetchone()
            if cross_source:
                provenance = item.metadata.get("provenance") or []
                cur.execute(
                    """
                    UPDATE radar_raw_items
                    SET last_seen_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP,
                        metadata = CASE
                            WHEN COALESCE(metadata -> 'provenance', '[]'::jsonb) @> %s::jsonb THEN metadata
                            ELSE jsonb_set(
                                metadata,
                                '{provenance}',
                                COALESCE(metadata -> 'provenance', '[]'::jsonb) || %s::jsonb,
                                true
                            )
                        END
                    WHERE id = %s
                    """,
                    (Json(provenance), Json(provenance), cross_source["id"]),
                )
                _requeue_orphaned_job_raw(cur, cross_source["id"], item)
                return StoreResult("duplicate", cross_source["id"], cross_source["deduplication_key"])
        cur.execute(
            """
            INSERT INTO radar_raw_items (
                source_key, external_id, deduplication_key,
                source_name, source_url, canonical_url,
                original_title, original_text, original_language,
                published_at, valid_from, valid_until,
                raw_category, raw_location, content_hash, metadata
            )
            VALUES (
                %s, NULLIF(%s, ''), %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (deduplication_key) DO NOTHING
            RETURNING id
            """,
            (
                item.source_key,
                item.external_id,
                deduplication_key,
                item.source_name,
                item.source_url,
                canonical_url,
                item.original_title,
                item.original_text,
                item.original_language,
                item.published_at,
                item.valid_from,
                item.valid_until,
                item.raw_category,
                item.raw_location,
                content_hash,
                Json(item.metadata),
            ),
        )
        inserted = cur.fetchone()
        if inserted:
            return StoreResult("inserted", inserted["id"], deduplication_key)

        cur.execute(
            """
            SELECT id, content_hash
            FROM radar_raw_items
            WHERE deduplication_key = %s
            """,
            (deduplication_key,),
        )
        existing = cur.fetchone()
        status = classify_existing_content(existing["content_hash"] if existing else None, content_hash)

        if status == "updated":
            cur.execute(
                """
                UPDATE radar_raw_items
                SET
                    last_seen_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    source_url = COALESCE(NULLIF(%s, ''), source_url),
                    canonical_url = COALESCE(NULLIF(%s, ''), canonical_url),
                    original_title = COALESCE(NULLIF(%s, ''), original_title),
                    original_text = COALESCE(NULLIF(%s, ''), original_text),
                    original_language = COALESCE(NULLIF(%s, ''), original_language),
                    published_at = COALESCE(%s, published_at),
                    valid_from = COALESCE(%s, valid_from),
                    valid_until = COALESCE(%s, valid_until),
                    raw_category = COALESCE(NULLIF(%s, ''), raw_category),
                    raw_location = COALESCE(NULLIF(%s, ''), raw_location),
                    content_hash = %s,
                    metadata = CASE WHEN %s::jsonb = '{}'::jsonb THEN metadata ELSE %s::jsonb END
                WHERE deduplication_key = %s
                RETURNING id
                """,
                (
                    item.source_url,
                    canonical_url,
                    item.original_title,
                    item.original_text,
                    item.original_language,
                    item.published_at,
                    item.valid_from,
                    item.valid_until,
                    item.raw_category,
                    item.raw_location,
                    content_hash,
                    Json(item.metadata),
                    Json(item.metadata),
                    deduplication_key,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE radar_raw_items
                SET last_seen_at = CURRENT_TIMESTAMP
                WHERE deduplication_key = %s
                RETURNING id
                """,
                (deduplication_key,),
            )
        updated = cur.fetchone()
        raw_item_id = (updated or existing or {}).get("id")
        if raw_item_id:
            _requeue_orphaned_job_raw(cur, raw_item_id, item)
        return StoreResult(status, raw_item_id, deduplication_key)
