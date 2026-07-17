import sys
import types
import unittest
from contextlib import contextmanager

from radar_engine.models import RawRadarItem
from radar_engine.storage import classify_existing_content, store_raw_item


class Json:
    def __init__(self, value):
        self.value = value


def install_storage_stubs(cursor):
    psycopg2 = types.ModuleType("psycopg2")
    extras = types.ModuleType("psycopg2.extras")
    extras.Json = Json
    database = types.ModuleType("database")
    db = types.ModuleType("database.db")

    @contextmanager
    def db_cursor(dict_cursor=False):
        yield None, cursor

    db.db_cursor = db_cursor
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras
    sys.modules["database"] = database
    sys.modules["database.db"] = db


class FakeCursor:
    def __init__(self, fetches):
        self.fetches = list(fetches)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.fetches.pop(0) if self.fetches else None


def raw_item(text="Body"):
    return RawRadarItem(
        source_key="boe",
        external_id="BOE-A-1",
        source_name="BOE",
        source_url="https://www.boe.es/test",
        original_title="Title",
        original_text=text,
        original_language="es",
        published_at=None,
        valid_from=None,
        valid_until=None,
        raw_category=None,
        raw_location=None,
        metadata={},
    )


class StorageTests(unittest.TestCase):
    def test_classify_existing_content(self):
        self.assertEqual(classify_existing_content("abc", "abc"), "duplicate")
        self.assertEqual(classify_existing_content("abc", "def"), "updated")

    def test_new_item_returns_inserted(self):
        cursor = FakeCursor([{"id": "new-id"}])
        install_storage_stubs(cursor)
        result = store_raw_item(raw_item())
        self.assertEqual(result.status, "inserted")
        self.assertTrue(result.deduplication_key)

    def test_existing_identical_item_returns_duplicate(self):
        item = raw_item()
        from radar_engine.deduplication import build_content_hash

        cursor = FakeCursor([None, {"id": "old-id", "content_hash": build_content_hash(item)}, {"id": "old-id"}])
        install_storage_stubs(cursor)
        result = store_raw_item(item)
        self.assertEqual(result.status, "duplicate")
        self.assertIn("last_seen_at", cursor.executed[-1][0])

    def test_existing_changed_item_returns_updated_without_empty_overwrite(self):
        cursor = FakeCursor([None, {"id": "old-id", "content_hash": "old"}, {"id": "old-id"}])
        install_storage_stubs(cursor)
        result = store_raw_item(raw_item("Changed"))
        self.assertEqual(result.status, "updated")
        self.assertIn("COALESCE(NULLIF", cursor.executed[-1][0])

    def test_cross_source_job_is_merged_without_second_raw_row(self):
        item = raw_item()
        item.source_key = "source_b"
        item.metadata = {
            "job_fingerprint": "same-job",
            "provenance": [{"source_key": "source_b", "external_id": "b-1", "url": item.source_url}],
        }
        cursor = FakeCursor([{"id": "source-a-id", "deduplication_key": "source_a:external:a-1"}])
        install_storage_stubs(cursor)
        result = store_raw_item(item)
        self.assertEqual(result.status, "duplicate")
        self.assertEqual(result.raw_item_id, "source-a-id")
        self.assertIn("provenance", cursor.executed[-1][0])
