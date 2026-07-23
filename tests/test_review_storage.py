import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from radar_engine.review.storage import (
    approve_candidate,
    load_review_queue,
    needs_edit_candidate,
    reject_candidate,
    review_status_report,
)


def queue_row(**overrides):
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
    }
    data.update(overrides)
    return data


class FakeCursor:
    def __init__(self, rows=None, rowcount=1, one=None):
        self.rows = rows or []
        self.one = one
        self.rowcount = rowcount
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


def fake_database(cursor):
    db = types.ModuleType("database.db")

    @contextmanager
    def db_cursor(dict_cursor=False):
        yield None, cursor

    db.db_cursor = db_cursor
    return db


class ReviewStorageTests(unittest.TestCase):
    def test_queue_loading_requires_summary_and_classification_and_excludes_reviewed(self):
        cursor = FakeCursor([queue_row()])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_review_queue(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].candidate_id, "candidate-1")
        sql, params = cursor.executed[0]
        self.assertIn("JOIN radar_ai_results", sql)
        self.assertIn("JOIN radar_ai_classifications", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("radar_reviews", sql)
        self.assertIn("actionability_gate", sql)
        self.assertIn("cls.primary_category <> 'job'", sql)
        self.assertIn("visa_sponsorship' = 'YES'", sql)
        self.assertIn("visa_sponsorship_evidence_verified", sql)
        self.assertIn("NULLIF(BTRIM", sql)
        self.assertEqual(params, (5,))

    def test_candidate_specific_loading_is_parameterized(self):
        cursor = FakeCursor([])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            self.assertEqual(load_review_queue(candidate_id="candidate-1"), [])
        sql, params = cursor.executed[0]
        self.assertIn("c.id = %s", sql)
        self.assertIn("actionability_gate", sql)
        self.assertIn("visa_sponsorship_evidence_verified", sql)
        self.assertEqual(params, ("candidate-1",))

    def test_approve_reject_and_needs_edit_insert_review_only(self):
        for func, status in (
            (approve_candidate, "approved"),
            (reject_candidate, "rejected"),
            (needs_edit_candidate, "needs_edit"),
        ):
            with self.subTest(status=status):
                cursor = FakeCursor(rowcount=1)
                with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
                    self.assertTrue(func("candidate-1", reviewed_by=123, admin_note="note"))
                sql, params = cursor.executed[0]
                self.assertIn("INSERT INTO radar_reviews", sql)
                self.assertIn("ON CONFLICT (candidate_id) DO NOTHING", sql)
                self.assertNotIn("radar_ai_results", sql)
                self.assertNotIn("radar_ai_classifications", sql)
                self.assertNotIn("radar_items", sql)
                self.assertEqual(params[:4], ("candidate-1", status, 123, "note"))

    def test_duplicate_review_returns_false(self):
        cursor = FakeCursor(rowcount=0)
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            self.assertFalse(approve_candidate("candidate-1", reviewed_by=123))

    def test_status_report_counts_queue_and_decisions(self):
        cursor = FakeCursor(
            rows=[
                {"review_status": "approved", "total": 2},
                {"review_status": "rejected", "total": 1},
                {"review_status": "needs_edit", "total": 3},
            ],
            one={"total": 4},
        )
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            report = review_status_report()
        self.assertEqual(report.pending, 4)
        self.assertEqual(report.approved, 2)
        self.assertEqual(report.rejected, 1)
        self.assertEqual(report.needs_edit, 3)
        sql_text = "\n".join(sql for sql, _ in cursor.executed)
        self.assertIn("actionability_gate", sql_text)
        self.assertIn("visa_sponsorship_evidence_verified", sql_text)

    def test_job_review_filter_requires_yes_evidence_and_deterministic_verification(self):
        cursor = FakeCursor([])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            load_review_queue(limit=10)
        sql, _ = cursor.executed[0]
        self.assertIn("ai.structured_data ->> 'visa_sponsorship' = 'YES'", sql)
        self.assertIn("ai.structured_data ->> 'visa_sponsorship_evidence'", sql)
        self.assertIn("ai.structured_data ->> 'visa_sponsorship_evidence_verified' = 'true'", sql)
        self.assertNotIn("relocation_support", sql)
        self.assertNotIn("apply_from_outside_spain", sql)

    def test_non_job_review_candidates_remain_eligible(self):
        cursor = FakeCursor([queue_row(primary_category="legal")])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            rows = load_review_queue(limit=10)
        self.assertEqual([row.classification.primary_category for row in rows], ["legal"])


if __name__ == "__main__":
    unittest.main()
