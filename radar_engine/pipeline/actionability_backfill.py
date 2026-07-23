from __future__ import annotations

from dataclasses import dataclass, field

from radar_engine.pipeline.actionability import (
    ACTIONABILITY_METADATA_KEY,
    apply_actionability_metadata,
    evaluate_actionability,
)
from radar_engine.pipeline.candidate import RadarCandidate


MAX_BACKFILL_LIMIT = 500


@dataclass
class ActionabilityBackfillReport:
    evaluated: int = 0
    passed: int = 0
    recovered: int = 0
    rejected: int = 0
    remaining: int = 0
    errors: list[str] = field(default_factory=list)


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


def backfill_actionability(limit: int = 50) -> ActionabilityBackfillReport:
    """Evaluate a bounded FIFO batch of legacy candidates without running AI or publication."""
    from psycopg2.extras import Json

    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), MAX_BACKFILL_LIMIT))
    report = ActionabilityBackfillReport()
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT *
            FROM radar_candidates
            WHERE candidate_status = 'rejected'
              AND lower(metadata ->> 'content_type') = 'job'
              AND metadata ->> 'rejection_reason' = 'low_practical_impact'
            ORDER BY created_at ASC, id ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (safe_limit,),
        )
        recovery_rows = cur.fetchall()
        for row in recovery_rows:
            candidate = _row_to_candidate(row)
            result = evaluate_actionability(candidate)
            apply_actionability_metadata(candidate, result)
            validation_issue = {
                "field": "actionability",
                "code": result.rejection_reason or "low_practical_impact",
                "message": "Candidate does not meet Radar actionability requirements.",
            }
            cur.execute(
                """
                UPDATE radar_candidates
                SET metadata = %s,
                    validation_errors = (
                        SELECT COALESCE(jsonb_agg(issue), '[]'::jsonb)
                        FROM jsonb_array_elements(COALESCE(validation_errors, '[]'::jsonb)) AS issue
                        WHERE NOT (
                            issue ->> 'field' = 'actionability'
                            AND issue ->> 'code' = 'low_practical_impact'
                        )
                    ) || %s::jsonb,
                    candidate_status = CASE WHEN %s THEN 'pending_ai' ELSE 'rejected' END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND candidate_status = 'rejected'
                  AND lower(metadata ->> 'content_type') = 'job'
                  AND metadata ->> 'rejection_reason' = 'low_practical_impact'
                RETURNING candidate_status
                """,
                (
                    Json(candidate.metadata),
                    Json([] if result.passed else [validation_issue]),
                    result.passed,
                    row["id"],
                ),
            )
            updated = cur.fetchone()
            if not updated:
                continue
            report.evaluated += 1
            if result.passed:
                report.passed += 1
                report.recovered += 1
            else:
                report.rejected += 1

        remaining_limit = max(0, safe_limit - report.evaluated)
        if remaining_limit == 0:
            rows = []
        else:
            cur.execute(
                """
                SELECT *
                FROM radar_candidates
                WHERE candidate_status = 'pending_ai'
                  AND NOT (metadata ? %s)
                ORDER BY created_at ASC, id ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (ACTIONABILITY_METADATA_KEY, remaining_limit),
            )
            rows = cur.fetchall()

        for row in rows:
            candidate = _row_to_candidate(row)
            result = evaluate_actionability(candidate)
            apply_actionability_metadata(candidate, result)
            validation_issue = {
                "field": "actionability",
                "code": result.rejection_reason or "low_practical_impact",
                "message": "Candidate does not meet Radar actionability requirements.",
            }
            cur.execute(
                """
                UPDATE radar_candidates
                SET metadata = %s,
                    validation_errors = CASE
                        WHEN %s THEN validation_errors
                        ELSE validation_errors || %s::jsonb
                    END,
                    candidate_status = CASE WHEN %s THEN candidate_status ELSE 'rejected' END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND candidate_status = 'pending_ai'
                  AND NOT (metadata ? %s)
                RETURNING candidate_status
                """,
                (
                    Json(candidate.metadata),
                    result.passed,
                    Json([] if result.passed else [validation_issue]),
                    result.passed,
                    row["id"],
                    ACTIONABILITY_METADATA_KEY,
                ),
            )
            updated = cur.fetchone()
            if not updated:
                continue
            report.evaluated += 1
            if result.passed:
                report.passed += 1
            else:
                report.rejected += 1

        cur.execute(
            """
            SELECT COUNT(*) AS remaining
            FROM radar_candidates
            WHERE (
                candidate_status = 'pending_ai'
                AND NOT (metadata ? %s)
            ) OR (
                candidate_status = 'rejected'
                AND lower(metadata ->> 'content_type') = 'job'
                AND metadata ->> 'rejection_reason' = 'low_practical_impact'
            )
            """,
            (ACTIONABILITY_METADATA_KEY,),
        )
        count_row = cur.fetchone()
        report.remaining = int(count_row["remaining"] if count_row else 0)
    return report
