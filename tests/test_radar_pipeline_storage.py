import sys
import types
import unittest
from contextlib import contextmanager

from radar_engine.pipeline.enricher import PIPELINE_VERSION
from radar_engine.pipeline.storage import (
    load_pending_raw_items,
    load_source_info,
    mark_raw_failed,
    mark_raw_rejected,
    store_candidate,
)
from radar_engine.pipeline.validator import ValidationResult, ValidationIssue
from tests.test_radar_candidate import make_candidate


class Json:
    def __init__(self, value):
        self.value = value


class FakeCursor:
    def __init__(self, fetches):
        self.fetches = list(fetches)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.fetches.pop(0) if self.fetches else None

    def fetchall(self):
        value = self.fetches.pop(0) if self.fetches else []
        return value


def install_db_stub(cursor):
    extras = types.ModuleType("psycopg2.extras")
    extras.Json = Json
    db = types.ModuleType("database.db")

    @contextmanager
    def db_cursor(dict_cursor=False):
        yield None, cursor

    db.db_cursor = db_cursor
    sys.modules["psycopg2.extras"] = extras
    sys.modules["database.db"] = db


class PipelineStorageTests(unittest.TestCase):
    def test_load_pending_raw_items_uses_limit(self):
        row = {
            "id": "raw-1",
            "source_key": "boe",
            "external_id": "BOE-A-1",
            "source_name": "BOE",
            "source_url": "https://www.boe.es/a",
            "canonical_url": None,
            "original_title": "Title",
            "original_text": "Body text long",
            "original_language": "es",
            "published_at": None,
            "valid_from": None,
            "valid_until": None,
            "raw_category": None,
            "raw_location": None,
            "metadata": {},
            "ingestion_status": "raw",
        }
        cursor = FakeCursor([[row]])
        install_db_stub(cursor)
        items = load_pending_raw_items(5)
        self.assertEqual(len(items), 1)
        self.assertEqual(cursor.executed[0][1], ("raw", 5))

    def test_load_source_info(self):
        cursor = FakeCursor([
            {
                "name": "BOE",
                "category": "Government",
                "source_url": "https://www.boe.es/",
                "source_type": "official",
                "trust_level": 5,
                "country": "Spain",
                "city": None,
            }
        ])
        install_db_stub(cursor)
        source = load_source_info("boe")
        self.assertEqual(source.name, "BOE")
        self.assertEqual(source.trust_level, 5)

    def test_store_candidate_created_and_parameterized(self):
        cursor = FakeCursor([{"id": "candidate-1"}])
        install_db_stub(cursor)
        result = store_candidate(make_candidate(), ValidationResult(True), PIPELINE_VERSION)
        self.assertEqual(result.status, "created")
        sql_text = "\n".join(sql for sql, _ in cursor.executed)
        self.assertNotIn("radar_items", sql_text)
        self.assertIn("%s", cursor.executed[0][0])

    def test_existing_candidate_returns_already_exists(self):
        cursor = FakeCursor([None, {"id": "candidate-1", "candidate_status": "pending_ai"}])
        install_db_stub(cursor)
        result = store_candidate(make_candidate(), ValidationResult(True), PIPELINE_VERSION)
        self.assertEqual(result.status, "already_exists")

    def test_rejected_candidate_stores_validation_errors(self):
        cursor = FakeCursor([{"id": "candidate-2"}])
        install_db_stub(cursor)
        validation = ValidationResult(False, [ValidationIssue("title", "blank", "missing")])
        result = mark_raw_rejected(make_candidate(), validation, PIPELINE_VERSION)
        self.assertEqual(result.status, "rejected")

    def test_mark_raw_failed(self):
        cursor = FakeCursor([{"id": "raw-1"}])
        install_db_stub(cursor)
        result = mark_raw_failed("raw-1", "boom")
        self.assertEqual(result.status, "failed")
        self.assertIn("candidate_failed", cursor.executed[0][1])
