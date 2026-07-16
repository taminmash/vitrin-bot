from __future__ import annotations

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.review.models import (
    RadarReviewDecision,
    RadarReviewQueueItem,
    RadarSummaryForReview,
    ReviewQueueReport,
)


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


def _row_to_queue_item(row) -> RadarReviewQueueItem:
    return RadarReviewQueueItem(
        candidate_id=str(row["candidate_id"]),
        candidate=_row_to_candidate(row),
        summary=RadarSummaryForReview(
            ai_result_id=str(row["ai_result_id"]),
            headline=row["ai_headline"],
            summary=row["ai_summary"],
            why_it_matters=row["ai_why_it_matters"],
            confidence=row["ai_confidence"],
        ),
        classification=RadarClassificationResult(
            candidate_id=str(row["candidate_id"]),
            primary_category=row["primary_category"],
            category_tags=row.get("category_tags") or [],
            audience_tags=row.get("audience_tags") or [],
            cities=row.get("cities") or [],
            geographic_scope=row["geographic_scope"],
            urgency=row["urgency"],
            priority_score=row["priority_score"],
            confidence=row["classification_confidence"],
            model_name=row["classification_model"],
            prompt_version=row["classification_prompt_version"],
            processing_time_ms=row["classification_latency"],
        ),
    )


def load_review_queue(limit: int = 50, candidate_id: str | None = None) -> list[RadarReviewQueueItem]:
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
                    ai.why_it_matters AS ai_why_it_matters,
                    ai.confidence AS ai_confidence,
                    cls.primary_category,
                    cls.category_tags,
                    cls.audience_tags,
                    cls.cities,
                    cls.geographic_scope,
                    cls.urgency,
                    cls.priority_score,
                    cls.confidence AS classification_confidence,
                    cls.model AS classification_model,
                    cls.prompt_version AS classification_prompt_version,
                    cls.latency AS classification_latency
                FROM radar_candidates c
                JOIN radar_ai_results ai ON ai.candidate_id = c.id
                JOIN radar_ai_classifications cls ON cls.candidate_id = c.id
                WHERE c.id = %s
                  AND c.metadata -> 'actionability_gate' ->> 'passed' = 'true'
                  AND NOT EXISTS (
                    SELECT 1 FROM radar_reviews reviews WHERE reviews.candidate_id = c.id
                  )
                LIMIT 1
                """,
                (candidate_id,),
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
                    ai.why_it_matters AS ai_why_it_matters,
                    ai.confidence AS ai_confidence,
                    cls.primary_category,
                    cls.category_tags,
                    cls.audience_tags,
                    cls.cities,
                    cls.geographic_scope,
                    cls.urgency,
                    cls.priority_score,
                    cls.confidence AS classification_confidence,
                    cls.model AS classification_model,
                    cls.prompt_version AS classification_prompt_version,
                    cls.latency AS classification_latency
                FROM radar_candidates c
                JOIN radar_ai_results ai ON ai.candidate_id = c.id
                JOIN radar_ai_classifications cls ON cls.candidate_id = c.id
                WHERE c.metadata -> 'actionability_gate' ->> 'passed' = 'true'
                  AND NOT EXISTS (
                    SELECT 1 FROM radar_reviews reviews WHERE reviews.candidate_id = c.id
                )
                ORDER BY cls.created_at ASC
                LIMIT %s
                """,
                (safe_limit,),
            )
        return [_row_to_queue_item(row) for row in cur.fetchall()]


def _store_decision(decision: RadarReviewDecision) -> bool:
    from database.db import db_cursor

    with db_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO radar_reviews (
                candidate_id, review_status, reviewed_by, reviewed_at, admin_note
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (candidate_id) DO NOTHING
            """,
            (
                decision.candidate_id,
                decision.review_status,
                decision.reviewed_by,
                decision.admin_note,
            ),
        )
        return bool(getattr(cur, "rowcount", 0))


def approve_candidate(candidate_id: str, reviewed_by: int | None = None, admin_note: str | None = None) -> bool:
    return _store_decision(RadarReviewDecision(candidate_id, "approved", reviewed_by, admin_note))


def reject_candidate(candidate_id: str, reviewed_by: int | None = None, admin_note: str | None = None) -> bool:
    return _store_decision(RadarReviewDecision(candidate_id, "rejected", reviewed_by, admin_note))


def needs_edit_candidate(candidate_id: str, reviewed_by: int | None = None, admin_note: str | None = None) -> bool:
    return _store_decision(RadarReviewDecision(candidate_id, "needs_edit", reviewed_by, admin_note))


def review_status_report() -> ReviewQueueReport:
    from database.db import db_cursor

    report = ReviewQueueReport()
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT review_status, COUNT(*) AS total
            FROM radar_reviews
            GROUP BY review_status
            """
        )
        for row in cur.fetchall():
            status = row.get("review_status")
            if status in {"approved", "rejected", "needs_edit"}:
                setattr(report, status, int(row.get("total") or 0))
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM radar_candidates c
            JOIN radar_ai_results ai ON ai.candidate_id = c.id
            JOIN radar_ai_classifications cls ON cls.candidate_id = c.id
            WHERE c.metadata -> 'actionability_gate' ->> 'passed' = 'true'
              AND NOT EXISTS (
                SELECT 1 FROM radar_reviews reviews WHERE reviews.candidate_id = c.id
            )
            """
        )
        row = cur.fetchone()
        report.pending = int((row or {}).get("total") or 0)
    return report
