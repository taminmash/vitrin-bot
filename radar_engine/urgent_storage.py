from __future__ import annotations

import json
from urllib.parse import urlparse

from radar_engine.promotion.mapper import map_approved_source_to_radar_item, validate_mapped_payload
from radar_engine.promotion.storage import _insert_radar_item
from radar_engine.review.storage import load_review_queue


AUDIT_PREFIX = "[urgent-auto-publish]"


def load_urgent_candidates(limit: int = 50):
    from database.db import db_cursor

    safe_limit = max(1, min(int(limit), 200))
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT c.id
            FROM radar_candidates c
            JOIN radar_ai_results ai ON ai.candidate_id = c.id
            JOIN radar_ai_classifications cls ON cls.candidate_id = c.id
            WHERE cls.primary_category = 'alert'
              AND c.metadata -> 'actionability_gate' ->> 'passed' = 'true'
              AND NOT (c.metadata ? 'urgent_auto_publish')
              AND NOT EXISTS (SELECT 1 FROM radar_reviews r WHERE r.candidate_id = c.id)
            ORDER BY cls.created_at ASC
            LIMIT %s
            """,
            (safe_limit,),
        )
        candidate_ids = [str(row["id"]) for row in cur.fetchall()]
    return [item for candidate_id in candidate_ids for item in load_review_queue(candidate_id=candidate_id)]


def is_trusted_urgent_source(candidate) -> bool:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT source_url
            FROM source_registry
            WHERE is_active = true
              AND name = %s
              AND source_type = 'official'
              AND trust_level >= 4
            """,
            (candidate.source_name,),
        )
        rows = cur.fetchall()
    candidate_host = (urlparse(candidate.source_url or "").hostname or "").casefold()
    for row in rows:
        registry_host = (urlparse(row.get("source_url") or "").hostname or "").casefold()
        if registry_host and (candidate_host == registry_host or candidate_host.endswith(f".{registry_host}")):
            return True
    return False


def load_urgent_safety_state() -> dict:
    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            SELECT
                MAX(reviewed_at) AS last_published_at,
                COUNT(*) FILTER (WHERE reviewed_at >= CURRENT_DATE) AS published_today
            FROM radar_reviews
            WHERE review_status = 'approved'
              AND admin_note LIKE %s
            """,
            (f"{AUDIT_PREFIX}%",),
        )
        row = cur.fetchone() or {}
    return {
        "last_published_at": row.get("last_published_at"),
        "published_today": int(row.get("published_today") or 0),
    }


def prepare_urgent_radar_item(item, decision) -> dict:
    payload = map_approved_source_to_radar_item(item)
    errors = validate_mapped_payload(payload)
    if errors:
        raise ValueError(str(errors))
    audit = {
        "candidate_id": item.candidate_id,
        "reason": "verified high-confidence urgent alert",
        "score": decision.score,
        "confidence": decision.confidence,
    }
    structured = dict(payload.fields.get("structured_data") or {})
    structured["urgent_auto_publish"] = audit
    payload.fields["structured_data"] = structured

    from database.db import db_cursor

    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute("SELECT metadata FROM radar_candidates WHERE id = %s FOR UPDATE", (item.candidate_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("candidate not found")
        if (row.get("metadata") or {}).get("urgent_auto_publish"):
            raise ValueError("candidate already has an urgent auto-publication decision")
        radar_item = _insert_radar_item(cur, payload.fields)
        cur.execute(
            """
            UPDATE radar_candidates
            SET metadata = metadata || %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (json.dumps({"urgent_auto_publish": {**audit, "status": "prepared", "radar_item_id": str(radar_item["id"])}}), item.candidate_id),
        )
    return radar_item


def record_urgent_outcome(item, radar_item: dict, decision, result) -> None:
    from database.db import db_cursor

    status = "published" if result.published or result.already_published else "failed"
    audit = {
        "status": status,
        "radar_item_id": str(radar_item["id"]),
        "reason": "verified high-confidence urgent alert",
        "score": decision.score,
        "confidence": decision.confidence,
        "publication_status": result.status,
        "telegram_message_id": result.telegram_message_id,
        "error": result.error,
    }
    with db_cursor(dict_cursor=True) as (_, cur):
        cur.execute(
            """
            UPDATE radar_candidates
            SET metadata = jsonb_set(metadata, '{urgent_auto_publish}', %s::jsonb, true),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (json.dumps(audit), item.candidate_id),
        )
        if status != "published":
            return
        note = (
            f"{AUDIT_PREFIX} reason=verified high-confidence urgent alert; "
            f"score={decision.score}; confidence={decision.confidence:.2f}"
        )
        cur.execute(
            """
            INSERT INTO radar_reviews (candidate_id, review_status, reviewed_at, admin_note)
            VALUES (%s, 'approved', CURRENT_TIMESTAMP, %s)
            ON CONFLICT (candidate_id) DO NOTHING
            RETURNING id
            """,
            (item.candidate_id, note),
        )
        review = cur.fetchone()
        if not review:
            cur.execute("SELECT id FROM radar_reviews WHERE candidate_id = %s", (item.candidate_id,))
            review = cur.fetchone()
        cur.execute(
            """
            INSERT INTO radar_promotions (candidate_id, review_id, radar_item_id, promotion_status, promoted_by)
            VALUES (%s, %s, %s, 'completed', NULL)
            ON CONFLICT (candidate_id) DO NOTHING
            """,
            (item.candidate_id, review["id"], radar_item["id"]),
        )
