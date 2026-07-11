from __future__ import annotations

import json

from radar_engine.classification.models import ClassificationSource, RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate


def _row_to_candidate(row) -> RadarCandidate:
    return RadarCandidate(
        raw_item_id=str(row["raw_item_id"]),
        source_key=row["source_key"],
        source_name=row["source_name"],
        external_id=row.get("external_id"),
        title=row["title"],
        body=row["body"],
        language=row["language"],
        source_url=row["source_url"],
        canonical_url=row.get("canonical_url"),
        published_at=row.get("published_at"),
        valid_from=row.get("valid_from"),
        valid_until=row.get("valid_until"),
        source_category=row.get("source_category"),
        source_location=row.get("source_location"),
        source_type=row["source_type"],
        trust_level=row["trust_level"],
        country=row.get("country") or "Spain",
        candidate_status=row.get("candidate_status") or "pending_ai",
        metadata=row.get("metadata") or {},
    )


def _row_to_source(row) -> ClassificationSource:
    return ClassificationSource(
        candidate_id=str(row["candidate_id"]),
        ai_result_id=str(row["ai_result_id"]),
        candidate=_row_to_candidate(row),
        ai_headline=row["ai_headline"],
        ai_summary=row["ai_summary"],
        ai_why_it_matters=row["ai_why_it_matters"],
    )


def load_pending_classification_candidates(
    limit: int = 50,
    candidate_id: str | None = None,
) -> list[ClassificationSource]:
    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), 200))
    with db_cursor(dict_cursor=True) as (_, cur):
        if candidate_id:
            cur.execute(
                """
                SELECT
                    c.id AS candidate_id,
                    c.raw_item_id,
                    c.source_key,
                    c.source_name,
                    c.external_id,
                    c.title,
                    c.body,
                    c.language,
                    c.source_url,
                    c.canonical_url,
                    c.published_at,
                    c.valid_from,
                    c.valid_until,
                    c.source_category,
                    c.source_location,
                    c.country,
                    c.source_type,
                    c.trust_level,
                    c.candidate_status,
                    c.metadata,
                    ai.id AS ai_result_id,
                    ai.headline AS ai_headline,
                    ai.summary AS ai_summary,
                    ai.why_it_matters AS ai_why_it_matters
                FROM radar_candidates c
                JOIN radar_ai_results ai ON ai.candidate_id = c.id
                WHERE c.id = %s
                  AND c.candidate_status = %s
                  AND NOT EXISTS (
                    SELECT 1
                    FROM radar_ai_classifications cls
                    WHERE cls.candidate_id = c.id
                  )
                LIMIT 1
                """,
                (candidate_id, "pending_ai"),
            )
        else:
            cur.execute(
                """
                SELECT
                    c.id AS candidate_id,
                    c.raw_item_id,
                    c.source_key,
                    c.source_name,
                    c.external_id,
                    c.title,
                    c.body,
                    c.language,
                    c.source_url,
                    c.canonical_url,
                    c.published_at,
                    c.valid_from,
                    c.valid_until,
                    c.source_category,
                    c.source_location,
                    c.country,
                    c.source_type,
                    c.trust_level,
                    c.candidate_status,
                    c.metadata,
                    ai.id AS ai_result_id,
                    ai.headline AS ai_headline,
                    ai.summary AS ai_summary,
                    ai.why_it_matters AS ai_why_it_matters
                FROM radar_candidates c
                JOIN radar_ai_results ai ON ai.candidate_id = c.id
                WHERE c.candidate_status = %s
                  AND NOT EXISTS (
                    SELECT 1
                    FROM radar_ai_classifications cls
                    WHERE cls.candidate_id = c.id
                  )
                ORDER BY c.created_at ASC
                LIMIT %s
                """,
                ("pending_ai", safe_limit),
            )
        return [_row_to_source(row) for row in cur.fetchall()]


def store_classification_result(
    result: RadarClassificationResult,
    ai_result_id: str | None = None,
) -> None:
    from database.db import db_cursor

    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO radar_ai_classifications (
                candidate_id, ai_result_id, primary_category, category_tags,
                audience_tags, cities, geographic_scope, urgency,
                priority_score, confidence, model, prompt_version, latency
            )
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (candidate_id) DO NOTHING
            """,
            (
                result.candidate_id,
                ai_result_id,
                result.primary_category,
                json.dumps(result.category_tags, ensure_ascii=False),
                json.dumps(result.audience_tags, ensure_ascii=False),
                json.dumps(result.cities, ensure_ascii=False),
                result.geographic_scope,
                result.urgency,
                result.priority_score,
                result.confidence,
                result.model_name,
                result.prompt_version,
                result.processing_time_ms,
            ),
        )
