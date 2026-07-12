import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from radar_engine.promotion.storage import load_approved_unpromoted_candidates, promote_candidate
from tests.test_promotion_mapper import make_source


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
        self.assertEqual(params, (5,))

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
        radar_params = cursor.executed[1][1]
        self.assertIn("ready", radar_params)
        self.assertIn("not_sent", radar_params)

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


if __name__ == "__main__":
    unittest.main()
