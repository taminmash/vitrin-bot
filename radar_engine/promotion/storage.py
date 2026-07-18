from __future__ import annotations

import json

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.promotion.mapper import map_approved_source_to_radar_item, validate_mapped_payload
from radar_engine.promotion.models import ApprovedPromotionSource, PromotionResult
from radar_engine.review.models import RadarSummaryForReview


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


def _row_to_source(row) -> ApprovedPromotionSource:
    promotion_id = row.get("promotion_id")
    radar_item_id = row.get("promoted_radar_item_id")
    return ApprovedPromotionSource(
        candidate_id=str(row["candidate_id"]),
        review_id=str(row["review_id"]),
        review_status=row["review_status"],
        candidate=_row_to_candidate(row),
        summary=RadarSummaryForReview(
            ai_result_id=str(row["ai_result_id"]),
            headline=row["ai_headline"],
            summary=row["ai_summary"],
            why_it_matters=row["ai_why_it_matters"],
            confidence=row["ai_confidence"],
            structured_data=row.get("ai_structured_data") or {},
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
        already_promoted=bool(promotion_id or radar_item_id),
        promotion_id=str(promotion_id) if promotion_id else None,
        radar_item_id=str(radar_item_id) if radar_item_id else None,
    )


def _approved_source_select(extra_where: str = "", limit_clause: str = "") -> str:
    return f"""
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
            ai.structured_data AS ai_structured_data,
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
            cls.latency AS classification_latency,
            reviews.id AS review_id,
            reviews.review_status,
            promotions.id AS promotion_id,
            promotions.radar_item_id AS promoted_radar_item_id
        FROM radar_candidates c
        JOIN radar_ai_results ai ON ai.candidate_id = c.id
        JOIN radar_ai_classifications cls ON cls.candidate_id = c.id
        JOIN radar_reviews reviews ON reviews.candidate_id = c.id
        LEFT JOIN radar_promotions promotions ON promotions.candidate_id = c.id
        WHERE reviews.review_status = 'approved'
          {extra_where}
        ORDER BY reviews.reviewed_at ASC NULLS LAST, reviews.created_at ASC
        {limit_clause}
    """


def load_approved_unpromoted_candidates(
    limit: int = 50,
    candidate_id: str | None = None,
) -> list[ApprovedPromotionSource]:
    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), 200))
    with db_cursor(dict_cursor=True) as (_, cur):
        if candidate_id:
            cur.execute(
                _approved_source_select("AND c.id = %s", "LIMIT 1"),
                (candidate_id,),
            )
        else:
            cur.execute(
                _approved_source_select("AND promotions.id IS NULL", "LIMIT %s"),
                (safe_limit,),
            )
        return [_row_to_source(row) for row in cur.fetchall()]


def get_approved_promotion_source(candidate_id: str) -> ApprovedPromotionSource | None:
    rows = load_approved_unpromoted_candidates(candidate_id=candidate_id)
    return rows[0] if rows else None


def _insert_radar_item(cur, fields: dict) -> dict:
    allowed = {
        "title",
        "summary",
        "body",
        "type",
        "category",
        "category_tags",
        "city",
        "province",
        "country",
        "start_date",
        "end_date",
        "source_url",
        "source_name",
        "urgency",
        "priority_score",
        "audience_tags",
        "is_verified",
        "expires_at",
        "channel_published_at",
        "ai_summary",
        "ai_reason",
        "ai_tags",
        "ai_priority",
        "structured_data",
        "original_text",
        "original_language",
    }
    payload = {key: value for key, value in fields.items() if key in allowed}
    payload["content_status"] = "ready"
    payload["channel_status"] = "not_sent"
    payload["is_published"] = False
    payload["published_at"] = None
    payload["channel_published_at"] = None
    columns = list(payload.keys())
    values = [
        json.dumps(payload[column], ensure_ascii=False)
        if column in ("audience_tags", "ai_tags", "category_tags", "structured_data")
        else payload[column]
        for column in columns
    ]
    placeholders = []
    for column in columns:
        placeholders.append(
            "%s::jsonb" if column in ("audience_tags", "ai_tags", "category_tags", "structured_data") else "%s"
        )
    cur.execute(
        f"""
        INSERT INTO radar_items ({", ".join(columns)})
        VALUES ({", ".join(placeholders)})
        RETURNING *
        """,
        values,
    )
    return dict(cur.fetchone())


def promote_candidate(source: ApprovedPromotionSource, promoted_by: int | None = None) -> PromotionResult:
    if source.already_promoted:
        return PromotionResult(
            candidate_id=source.candidate_id,
            status="already_promoted",
            radar_item_id=source.radar_item_id,
            promotion_id=source.promotion_id,
        )
    payload = map_approved_source_to_radar_item(source)
    errors = validate_mapped_payload(payload)
    if errors:
        return PromotionResult(candidate_id=source.candidate_id, status="rejected", errors=errors)

    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            "SELECT id, radar_item_id FROM radar_promotions WHERE candidate_id = %s",
            (source.candidate_id,),
        )
        existing = cur.fetchone()
        if existing:
            return PromotionResult(
                candidate_id=source.candidate_id,
                status="already_promoted",
                radar_item_id=str(existing["radar_item_id"]),
                promotion_id=str(existing["id"]),
            )
        item = _insert_radar_item(cur, payload.fields)
        cur.execute(
            """
            INSERT INTO radar_promotions (
                candidate_id, review_id, radar_item_id, promotion_status, promoted_by
            )
            VALUES (%s, %s, %s, 'completed', %s)
            RETURNING id
            """,
            (source.candidate_id, source.review_id, item["id"], promoted_by),
        )
        promotion = cur.fetchone()
        return PromotionResult(
            candidate_id=source.candidate_id,
            status="created",
            radar_item_id=str(item["id"]),
            promotion_id=str(promotion["id"]),
        )
