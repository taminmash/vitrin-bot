from __future__ import annotations

from radar_engine.ai.models import AITaskResult, StoredAICandidate
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


def load_pending_ai_candidates(limit: int = 50, candidate_id: str | None = None) -> list[StoredAICandidate]:
    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), 200))
    with db_cursor(dict_cursor=True) as (_, cur):
        if candidate_id:
            cur.execute(
                """
                SELECT *
                FROM radar_candidates
                WHERE id = %s AND candidate_status = %s
                  AND metadata -> 'actionability_gate' ->> 'passed' = 'true'
                  AND NOT EXISTS (
                    SELECT 1 FROM radar_ai_results WHERE radar_ai_results.candidate_id = radar_candidates.id
                  )
                LIMIT 1
                """,
                (candidate_id, "pending_ai"),
            )
        else:
            cur.execute(
                """
                SELECT *
                FROM radar_candidates
                WHERE candidate_status = %s
                  AND metadata -> 'actionability_gate' ->> 'passed' = 'true'
                  AND NOT EXISTS (
                    SELECT 1 FROM radar_ai_results WHERE radar_ai_results.candidate_id = radar_candidates.id
                  )
                ORDER BY created_at ASC
                LIMIT %s
                """,
                ("pending_ai", safe_limit),
            )
        rows = cur.fetchall()
        return [StoredAICandidate(candidate_id=str(row["id"]), candidate=_row_to_candidate(row)) for row in rows]


def store_ai_result(candidate_id: str, result: AITaskResult) -> None:
    import json

    from database.db import db_cursor

    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO radar_ai_results (
                candidate_id, headline, summary, why_it_matters,
                confidence, model, prompt_version, latency, structured_data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (candidate_id) DO NOTHING
            """,
            (
                candidate_id,
                result.headline,
                result.short_summary,
                result.why_it_matters,
                result.confidence,
                result.model_name,
                result.prompt_version,
                result.processing_time_ms,
                json.dumps(result.structured_data, ensure_ascii=False),
            ),
        )
