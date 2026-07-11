from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from radar_engine.pipeline.candidate import RadarCandidate, SourceInfo, StoredRawRadarItem
from radar_engine.pipeline.validator import ValidationResult


CandidateStoreStatus = Literal["created", "already_exists", "rejected", "failed"]


@dataclass
class CandidateStoreResult:
    status: CandidateStoreStatus
    candidate_id: str | None
    raw_item_id: str


def row_to_stored_raw(row) -> StoredRawRadarItem:
    return StoredRawRadarItem(
        id=str(row["id"]),
        source_key=row["source_key"],
        external_id=row.get("external_id"),
        source_name=row["source_name"],
        source_url=row["source_url"],
        canonical_url=row.get("canonical_url"),
        original_title=row["original_title"],
        original_text=row["original_text"],
        original_language=row["original_language"],
        published_at=row.get("published_at"),
        valid_from=row.get("valid_from"),
        valid_until=row.get("valid_until"),
        raw_category=row.get("raw_category"),
        raw_location=row.get("raw_location"),
        metadata=row.get("metadata") or {},
        ingestion_status=row.get("ingestion_status") or "raw",
        first_seen_at=row.get("first_seen_at"),
        last_seen_at=row.get("last_seen_at"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def load_pending_raw_items(limit: int = 100) -> list[StoredRawRadarItem]:
    safe_limit = max(1, min(int(limit), 500))
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM radar_raw_items
            WHERE ingestion_status = %s
            ORDER BY first_seen_at ASC, created_at ASC
            LIMIT %s
            """,
            ("raw", safe_limit),
        )
        return [row_to_stored_raw(row) for row in cur.fetchall()]


def load_source_info(source_key: str) -> SourceInfo | None:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT name, category, source_url, source_type, trust_level, country, city
            FROM source_registry
            WHERE name = %s OR lower(name) = lower(%s)
            ORDER BY is_active DESC, trust_level DESC
            LIMIT 1
            """,
            (source_key, source_key),
        )
        row = cur.fetchone()
        if not row:
            return None
        return SourceInfo(
            source_key=source_key,
            name=row["name"],
            category=row.get("category"),
            source_type=row["source_type"],
            trust_level=row["trust_level"],
            country=row.get("country") or "Spain",
            city=row.get("city"),
        )


def validation_errors_payload(validation_result: ValidationResult) -> list[dict[str, str]]:
    return validation_result.as_dicts()


def _store_candidate_with_status(
    candidate: RadarCandidate,
    validation_result: ValidationResult,
    pipeline_version: str,
    status: str,
    raw_status: str,
) -> CandidateStoreResult:
    from psycopg2.extras import Json

    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            INSERT INTO radar_candidates (
                raw_item_id, source_key, source_name, external_id,
                title, body, language, source_url, canonical_url,
                published_at, valid_from, valid_until,
                source_category, source_location, country, source_type, trust_level,
                candidate_status, metadata, validation_errors, pipeline_version
            )
            VALUES (
                %s, %s, %s, NULLIF(%s, ''),
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (raw_item_id) DO NOTHING
            RETURNING id
            """,
            (
                candidate.raw_item_id,
                candidate.source_key,
                candidate.source_name,
                candidate.external_id,
                candidate.title,
                candidate.body,
                candidate.language,
                candidate.source_url,
                candidate.canonical_url,
                candidate.published_at,
                candidate.valid_from,
                candidate.valid_until,
                candidate.source_category,
                candidate.source_location,
                candidate.country,
                candidate.source_type,
                candidate.trust_level,
                status,
                Json(candidate.metadata),
                Json(validation_errors_payload(validation_result)),
                pipeline_version,
            ),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """
                UPDATE radar_raw_items
                SET ingestion_status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (raw_status, candidate.raw_item_id),
            )
            return CandidateStoreResult("created" if status == "pending_ai" else "rejected", str(row["id"]), candidate.raw_item_id)

        cur.execute("SELECT id, candidate_status FROM radar_candidates WHERE raw_item_id = %s", (candidate.raw_item_id,))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE radar_raw_items
                SET ingestion_status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (raw_status, candidate.raw_item_id),
            )
            return CandidateStoreResult("already_exists", str(existing["id"]), candidate.raw_item_id)
        return CandidateStoreResult("failed", None, candidate.raw_item_id)


def store_candidate(
    candidate: RadarCandidate,
    validation_result: ValidationResult,
    pipeline_version: str,
) -> CandidateStoreResult:
    return _store_candidate_with_status(candidate, validation_result, pipeline_version, "pending_ai", "candidate_created")


def mark_raw_rejected(
    candidate: RadarCandidate,
    validation_result: ValidationResult,
    pipeline_version: str,
) -> CandidateStoreResult:
    return _store_candidate_with_status(candidate, validation_result, pipeline_version, "rejected", "candidate_rejected")


def mark_raw_failed(raw_item_id, error_message: str | None = None) -> CandidateStoreResult:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_raw_items
            SET ingestion_status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id
            """,
            ("candidate_failed", raw_item_id),
        )
        row = cur.fetchone()
        return CandidateStoreResult("failed", str(row["id"]) if row else None, str(raw_item_id))
