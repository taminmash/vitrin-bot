import sys
import types
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from radar_engine.promotion.storage import (
    _insert_radar_item,
    get_approved_promotion_source,
    load_approved_unpromoted_candidates,
    promote_candidate,
)
from tests.test_promotion_mapper import make_source


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def promotion_row(**overrides):
    data = {
        "candidate_id": "candidate-1",
        "raw_item_id": "raw-1",
        "source_key": "boe",
        "source_name": "BOE",
        "external_id": "external-1",
        "title": "Original title",
        "body": "Official original body",
        "language": "es",
        "source_url": "https://boe.es/test",
        "canonical_url": "https://boe.es/test",
        "published_at": None,
        "valid_from": None,
        "valid_until": None,
        "source_category": "Government",
        "source_location": "Spain",
        "country": "Spain",
        "source_type": "official",
        "trust_level": 5,
        "candidate_status": "pending_ai",
        "metadata": {},
        "ai_result_id": "ai-1",
        "ai_headline": "AI headline",
        "ai_summary": "AI summary",
        "ai_why_it_matters": "AI reason",
        "ai_confidence": 0.8,
        "primary_category": "legal",
        "category_tags": ["legal"],
        "audience_tags": ["migration"],
        "cities": [],
        "geographic_scope": "national",
        "urgency": "high",
        "priority_score": 80,
        "classification_confidence": 0.9,
        "classification_model": "model",
        "classification_prompt_version": "radar-classification-v1",
        "classification_latency": 12,
        "review_id": "review-1",
        "review_status": "approved",
        "promotion_id": None,
        "promoted_radar_item_id": None,
    }
    data.update(overrides)
    return data


class FakeCursor:
    def __init__(self, rows=None, one=None, fail_on=None):
        self.rows = rows or []
        self.one_values = list(one or [])
        self.fail_on = fail_on or []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if any(marker in sql for marker in self.fail_on):
            raise RuntimeError("forced sql failure")

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if self.one_values:
            return self.one_values.pop(0)
        return None


class FakeConnection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def fake_database(cursor, connection=None):
    db = types.ModuleType("database.db")
    connection = connection or FakeConnection()

    @contextmanager
    def db_cursor(dict_cursor=False):
        try:
            yield connection, cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    db.db_cursor = db_cursor
    return db


class PromotionStorageTests(unittest.TestCase):
    def _insert_columns_and_params(self, cursor):
        sql, params = cursor.executed[1]
        column_text = sql.split("INSERT INTO radar_items (", 1)[1].split(")", 1)[0]
        return [column.strip() for column in column_text.split(",")], params

    def test_loader_requires_approved_review_and_excludes_existing_promotions(self):
        cursor = FakeCursor(rows=[promotion_row()])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_approved_unpromoted_candidates(limit=5)
        self.assertEqual(len(rows), 1)
        sql, params = cursor.executed[0]
        self.assertIn("JOIN radar_ai_results", sql)
        self.assertIn("JOIN radar_ai_classifications", sql)
        self.assertIn("JOIN radar_reviews", sql)
        self.assertIn("reviews.review_status = 'approved'", sql)
        self.assertIn("promotions.id IS NULL", sql)
        self.assertLess(sql.index("ORDER BY reviews.reviewed_at ASC NULLS LAST"), sql.index("LIMIT %s"))
        self.assertEqual(params, (5,))

    def test_loader_empty_and_multiple_results_preserve_review_order_clause(self):
        for rows, expected in (([], 0), ([promotion_row(), promotion_row(candidate_id="candidate-2")], 2)):
            with self.subTest(expected=expected):
                cursor = FakeCursor(rows=rows)
                with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
                    loaded = load_approved_unpromoted_candidates(limit=10)
                self.assertEqual(len(loaded), expected)
                sql, params = cursor.executed[0]
                self.assertIn("ORDER BY reviews.reviewed_at ASC NULLS LAST, reviews.created_at ASC", sql)
                self.assertNotIn("LIMIT %s\n        ORDER BY", sql)
                self.assertEqual(params, (10,))

    def test_candidate_specific_loader_reports_already_promoted(self):
        cursor = FakeCursor(
            rows=[
                promotion_row(
                    promotion_id="promotion-1",
                    promoted_radar_item_id="radar-1",
                )
            ]
        )
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_approved_unpromoted_candidates(candidate_id="candidate-1")
        self.assertTrue(rows[0].already_promoted)
        self.assertEqual(rows[0].radar_item_id, "radar-1")
        sql, params = cursor.executed[0]
        self.assertIn("c.id = %s", sql)
        self.assertLess(sql.index("ORDER BY reviews.reviewed_at ASC NULLS LAST"), sql.index("LIMIT 1"))
        self.assertNotIn("candidate-1", sql)
        self.assertEqual(params, ("candidate-1",))

    def test_candidate_specific_empty_result_returns_none(self):
        cursor = FakeCursor(rows=[])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_approved_unpromoted_candidates(candidate_id="missing")
        self.assertEqual(rows, [])
        sql, params = cursor.executed[0]
        self.assertIn("c.id = %s", sql)
        self.assertEqual(params, ("missing",))

    def test_get_candidate_returns_one_or_none(self):
        for rows, expected in (([promotion_row()], "candidate-1"), ([], None)):
            with self.subTest(expected=expected):
                cursor = FakeCursor(rows=rows)
                with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
                    source = get_approved_promotion_source("candidate-1")
                self.assertEqual(source.candidate_id if source else None, expected)
                sql, params = cursor.executed[0]
                self.assertIn("c.id = %s", sql)
                self.assertNotIn("candidate-1", sql)
                self.assertEqual(params, ("candidate-1",))

    def test_promote_creates_radar_item_and_audit_row_atomically(self):
        cursor = FakeCursor(
            one=[
                None,
                {"id": "radar-1", "content_status": "ready", "channel_status": "not_sent"},
                {"id": "promotion-1"},
            ]
        )
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = promote_candidate(make_source(), promoted_by=123)
        self.assertTrue(result.created)
        self.assertEqual(result.radar_item_id, "radar-1")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("INSERT INTO radar_items", sql)
        self.assertIn("INSERT INTO radar_promotions", sql)
        self.assertNotIn("channel_message_id", sql)
        self.assertNotIn("UPDATE radar_candidates", sql)
        self.assertNotIn("UPDATE radar_reviews", sql)
        self.assertNotIn("UPDATE radar_ai_results", sql)
        self.assertNotIn("UPDATE radar_ai_classifications", sql)
        columns, radar_params = self._insert_columns_and_params(cursor)
        values = dict(zip(columns, radar_params))
        self.assertEqual(values["content_status"], "ready")
        self.assertEqual(values["channel_status"], "not_sent")
        self.assertIs(values["is_published"], False)
        self.assertIsNone(values["published_at"])
        self.assertIsNone(values["channel_published_at"])
        self.assertNotIn("channel_message_id", columns)

    def test_mapped_payload_cannot_override_unpublished_ready_state(self):
        cursor = FakeCursor(one=[{"id": "radar-1"}])
        _insert_radar_item(
            cursor,
            {
                "title": "Title",
                "summary": "Summary",
                "type": "legal",
                "category": "legal",
                "source_url": "https://boe.es/test",
                "source_name": "BOE",
                "is_published": True,
                "published_at": datetime(2026, 7, 1, 9, 0),
                "channel_published_at": datetime(2026, 7, 1, 9, 1),
                "channel_message_id": 123,
                "content_status": "published",
                "channel_status": "published",
            },
        )
        sql, params = cursor.executed[0]
        column_text = sql.split("INSERT INTO radar_items (", 1)[1].split(")", 1)[0]
        columns = [column.strip() for column in column_text.split(",")]
        values = dict(zip(columns, params))
        self.assertEqual(values["content_status"], "ready")
        self.assertEqual(values["channel_status"], "not_sent")
        self.assertIs(values["is_published"], False)
        self.assertIsNone(values["published_at"])
        self.assertIsNone(values["channel_published_at"])
        self.assertNotIn("channel_message_id", columns)

    def test_duplicate_promotion_is_prevented_before_insert(self):
        cursor = FakeCursor(one=[{"id": "promotion-1", "radar_item_id": "radar-1"}])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = promote_candidate(make_source())
        self.assertTrue(result.already_promoted)
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertNotIn("INSERT INTO radar_items", sql)

    def test_insert_failure_does_not_create_promotion_row(self):
        connection = FakeConnection()
        cursor = FakeCursor(one=[None], fail_on=["INSERT INTO radar_items"])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor, connection)}):
            with self.assertRaises(RuntimeError):
                promote_candidate(make_source())
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertNotIn("INSERT INTO radar_promotions", sql)
        self.assertTrue(connection.rolled_back)

    def test_promotion_row_failure_rolls_back_radar_insert(self):
        connection = FakeConnection()
        cursor = FakeCursor(
            one=[None, {"id": "radar-1"}],
            fail_on=["INSERT INTO radar_promotions"],
        )
        with patch.dict(sys.modules, {"database.db": fake_database(cursor, connection)}):
            with self.assertRaises(RuntimeError):
                promote_candidate(make_source())
        self.assertTrue(connection.rolled_back)

    def test_ready_promotion_state_is_not_public_available_semantics(self):
        db_text = (PROJECT_ROOT / "database" / "db.py").read_text(encoding="utf-8")
        available_section = db_text.split("def available_radar_where():", 1)[1].split("def count_available_radar_by_type", 1)[0]
        admin_section = db_text.split("def list_admin_radar_items", 1)[1].split("def radar_content_status", 1)[0]
        self.assertIn("is_published = true", available_section)
        self.assertIn("COALESCE(content_status, 'draft') = 'ready'", admin_section)
        self.assertIn("COALESCE(content_status, 'draft') = 'published'", admin_section)

    def test_promotion_scope_does_not_call_publication_or_telegram(self):
        promotion_files = [
            PROJECT_ROOT / "radar_engine" / "promotion" / "engine.py",
            PROJECT_ROOT / "radar_engine" / "promotion" / "mapper.py",
            PROJECT_ROOT / "radar_engine" / "promotion" / "models.py",
            PROJECT_ROOT / "radar_engine" / "promotion" / "storage.py",
            PROJECT_ROOT / "scripts" / "run_radar_promotion.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in promotion_files)
        self.assertNotIn("publish_radar_item", combined)
        self.assertNotIn("send_message", combined)
        self.assertNotIn("send_photo", combined)
        self.assertNotIn("send_video", combined)
        self.assertNotIn("mark_radar_channel_published", combined)


if __name__ == "__main__":
    unittest.main()
