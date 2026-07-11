import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.classification.storage import (
    load_pending_classification_candidates,
    store_classification_result,
)


def classification_row(**overrides):
    data = {
        "candidate_id": "candidate-1",
        "raw_item_id": "raw-1",
        "source_key": "boe",
        "source_name": "BOE",
        "external_id": "external-1",
        "title": "Titulo oficial",
        "body": "Texto oficial suficiente para validar el candidato.",
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
        "ai_headline": "تیتر",
        "ai_summary": "خلاصه",
        "ai_why_it_matters": "دلیل",
    }
    data.update(overrides)
    return data


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


def fake_database(cursor):
    db = types.ModuleType("database.db")

    @contextmanager
    def db_cursor(dict_cursor=False):
        yield None, cursor

    db.db_cursor = db_cursor
    return db


class ClassificationStorageTests(unittest.TestCase):
    def test_loader_requires_ai_summary_and_excludes_existing_classification(self):
        cursor = FakeCursor([classification_row()])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_pending_classification_candidates(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].candidate_id, "candidate-1")
        sql, params = cursor.executed[0]
        self.assertIn("JOIN radar_ai_results", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("radar_ai_classifications", sql)
        self.assertEqual(params, ("pending_ai", 5))

    def test_candidate_specific_loading_uses_candidate_id(self):
        cursor = FakeCursor([])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_pending_classification_candidates(candidate_id="candidate-1")
        self.assertEqual(rows, [])
        sql, params = cursor.executed[0]
        self.assertIn("c.id = %s", sql)
        self.assertEqual(params, ("candidate-1", "pending_ai"))

    def test_store_uses_conflict_skip_and_json_arrays(self):
        cursor = FakeCursor()
        result = RadarClassificationResult(
            candidate_id="candidate-1",
            primary_category="legal",
            category_tags=["legal"],
            audience_tags=["migration"],
            cities=["Málaga"],
            geographic_scope="city",
            urgency="high",
            priority_score=80,
            confidence=0.9,
            model_name="model",
            prompt_version="radar-classification-v1",
            processing_time_ms=12,
        )
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            store_classification_result(result, ai_result_id="ai-1")
        sql, params = cursor.executed[0]
        self.assertIn("radar_ai_classifications", sql)
        self.assertIn("ON CONFLICT (candidate_id) DO NOTHING", sql)
        self.assertNotIn("UPDATE radar_candidates", sql)
        self.assertNotIn("radar_items", sql)
        self.assertEqual(params[0], "candidate-1")
        self.assertEqual(params[1], "ai-1")
        self.assertEqual(params[2], "legal")
        self.assertEqual(params[5], '["Málaga"]')
        self.assertEqual(params[6], "city")


if __name__ == "__main__":
    unittest.main()
