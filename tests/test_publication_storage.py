import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from radar_engine.publication.models import TelegramPublicationResponse
from radar_engine.publication.storage import (
    get_existing_successful_publication,
    load_ready_publication_items,
    reconcile_publication,
    record_publication_failure,
    record_publication_success,
)


def publication_row(**overrides):
    data = {
        "id": "radar-1",
        "title": "Title",
        "summary": "Summary",
        "content_status": "ready",
        "channel_status": "not_sent",
        "is_published": False,
        "channel_message_id": None,
    }
    data.update(overrides)
    return data


class FakeCursor:
    def __init__(self, rows=None, one=None):
        self.rows = rows or []
        self.one_values = list(one or [])
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

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
    db.row_to_dict = lambda row: dict(row) if row else None
    return db


class PublicationStorageTests(unittest.TestCase):
    def test_loader_selects_only_ready_unsent_unpublished_items(self):
        cursor = FakeCursor(rows=[publication_row()])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            items = load_ready_publication_items(limit=999)
        self.assertEqual(items[0].id, "radar-1")
        sql, params = cursor.executed[0]
        self.assertIn("COALESCE(content_status, 'draft') = 'ready'", sql)
        self.assertIn("COALESCE(channel_status, 'not_sent') = 'not_sent'", sql)
        self.assertIn("COALESCE(is_published, false) = false", sql)
        self.assertIn("channel_message_id IS NULL", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertEqual(params, (20,))

    def test_loader_can_include_failed_for_explicit_retry(self):
        cursor = FakeCursor(rows=[publication_row(channel_status="failed")])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            load_ready_publication_items(include_failed=True)
        sql, _ = cursor.executed[0]
        self.assertIn("COALESCE(channel_status, 'not_sent') IN ('not_sent', 'failed')", sql)

    def test_item_specific_loader_uses_id_and_limit_one(self):
        cursor = FakeCursor(rows=[publication_row(id="radar-2")])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            items = load_ready_publication_items(radar_item_id="radar-2")
        self.assertEqual(items[0].id, "radar-2")
        sql, params = cursor.executed[0]
        self.assertIn("WHERE id = %s", sql)
        self.assertIn("LIMIT 1", sql)
        self.assertEqual(params, ("radar-2",))

    def test_record_success_creates_audit_row_and_marks_item_published(self):
        cursor = FakeCursor(one=[{"id": "radar-1"}, {"id": "pub-1"}, {"id": "radar-1"}])
        response = TelegramPublicationResponse("@vitrinspain", 777, "https://t.me/vitrinspain/777")
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = record_publication_success("radar-1", response, published_by=123)
        self.assertTrue(result.published)
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("INSERT INTO radar_publications", sql)
        self.assertIn("ON CONFLICT (radar_item_id) WHERE publication_status = 'published'", sql)
        self.assertIn("UPDATE radar_items", sql)
        self.assertIn("content_status = 'published'", sql)
        self.assertIn("channel_status = 'published'", sql)
        self.assertIn("is_published = true", sql)
        self.assertIn("channel_message_id = %s", sql)
        self.assertNotIn("UPDATE radar_ai_results", sql)
        self.assertNotIn("UPDATE radar_reviews", sql)
        self.assertNotIn("UPDATE radar_promotions", sql)
        self.assertNotIn("send_message", sql)

    def test_duplicate_success_insert_is_reported_without_item_update(self):
        cursor = FakeCursor(one=[{"id": "radar-1"}, None])
        response = TelegramPublicationResponse("@vitrinspain", 777)
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = record_publication_success("radar-1", response)
        self.assertTrue(result.already_published)
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertNotIn("UPDATE radar_items", sql)

    def test_record_failure_updates_channel_status_only(self):
        cursor = FakeCursor()
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = record_publication_failure("radar-1", "@vitrinspain", "bad request", published_by=123)
        self.assertEqual(result.status, "telegram_failed")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("INSERT INTO radar_publications", sql)
        self.assertIn("'failed'", sql)
        self.assertIn("SET channel_status = 'failed'", sql)
        self.assertNotIn("content_status = 'published'", sql)
        self.assertNotIn("is_published = true", sql)

    def test_existing_successful_publication_reads_audit_row(self):
        cursor = FakeCursor(one=[{"id": "pub-1", "telegram_message_id": 777}])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            row = get_existing_successful_publication("radar-1")
        self.assertEqual(row["telegram_message_id"], 777)
        self.assertIn("publication_status = 'published'", cursor.executed[0][0])

    def test_reconcile_records_existing_message_without_sending(self):
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.record_publication_success"
        ) as record:
            record.return_value.status = "published"
            reconcile_publication("radar-1", 888, "@vitrinspain", "https://t.me/vitrinspain/888")
        args, kwargs = record.call_args
        self.assertEqual(args[0], "radar-1")
        self.assertEqual(args[1].telegram_message_id, 888)
        self.assertEqual(args[1].channel_post_url, "https://t.me/vitrinspain/888")


if __name__ == "__main__":
    unittest.main()
