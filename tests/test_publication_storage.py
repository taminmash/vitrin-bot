import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from radar_engine.publication.models import PublicationAttempt, TelegramPublicationResponse
from radar_engine.publication.storage import (
    claim_publication_attempt,
    complete_reconcilable_attempt,
    get_existing_successful_publication,
    load_ready_publication_items,
    mark_attempt_ambiguous,
    mark_attempt_cancelled,
    mark_attempt_completed,
    mark_attempt_failed,
    mark_attempt_sent,
    reconcile_publication,
    release_publication_attempt,
    record_publication_failure,
    record_publication_success,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def attempt_row(**overrides):
    data = {
        "id": "attempt-1",
        "radar_item_id": "radar-1",
        "attempt_token": "token-1",
        "attempt_status": "sending",
        "telegram_message_id": None,
        "channel_id": None,
        "channel_post_url": None,
        "last_error": None,
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

    def test_claim_inserts_single_active_sending_attempt(self):
        cursor = FakeCursor(one=[None, attempt_row()])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            claim = claim_publication_attempt("radar-1", claimed_by=123, ttl_seconds=600)
        self.assertTrue(claim.claimed)
        self.assertEqual(claim.attempt.attempt_status, "sending")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("expires_at <= CURRENT_TIMESTAMP", sql)
        self.assertIn("INSERT INTO radar_publication_attempts", sql)
        self.assertIn("ON CONFLICT (radar_item_id) WHERE attempt_status = 'sending'", sql)
        self.assertEqual(cursor.executed[2][1][2], 123)

    def test_active_sending_claim_blocks_second_sender(self):
        cursor = FakeCursor(one=[None, None, attempt_row()])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            claim = claim_publication_attempt("radar-1")
        self.assertTrue(claim.in_progress)
        self.assertEqual(claim.attempt.attempt_status, "sending")

    def test_expired_sending_claim_becomes_ambiguous_and_is_not_reclaimed(self):
        cursor = FakeCursor(one=[attempt_row(attempt_status="ambiguous")])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            claim = claim_publication_attempt("radar-1")
        self.assertTrue(claim.reconciliation_required)
        self.assertEqual(claim.attempt.attempt_status, "ambiguous")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("attempt_status = 'ambiguous'", sql)
        self.assertIn("expires_at <= CURRENT_TIMESTAMP", sql)
        self.assertNotIn("INSERT INTO radar_publication_attempts", sql)

    def test_ambiguous_and_sent_unpersisted_claims_are_not_reclaimed(self):
        for status in ("ambiguous", "sent_unpersisted"):
            cursor = FakeCursor(one=[attempt_row(attempt_status=status, telegram_message_id=999)])
            with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
                claim = claim_publication_attempt("radar-1")
            self.assertTrue(claim.reconciliation_required)
            self.assertEqual(claim.attempt.attempt_status, status)
            sql = "\n".join(statement for statement, _ in cursor.executed)
            self.assertNotIn("INSERT INTO radar_publication_attempts", sql)

    def test_attempt_status_transitions_are_parameterized(self):
        cursor = FakeCursor(one=[attempt_row(attempt_status="sent_unpersisted", telegram_message_id=777)])
        response = TelegramPublicationResponse("@vitrinspain", 777, "https://t.me/vitrinspain/777")
        attempt = PublicationAttempt("radar-1", "token-1", "sending")
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            sent = mark_attempt_sent(attempt, response)
        self.assertEqual(sent.attempt_status, "sent_unpersisted")
        sql, params = cursor.executed[0]
        self.assertIn("attempt_status = 'sent_unpersisted'", sql)
        self.assertEqual(params[:3], (777, "@vitrinspain", "https://t.me/vitrinspain/777"))

        cursor = FakeCursor()
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            mark_attempt_completed(attempt)
            mark_attempt_failed(attempt, "bad request")
            mark_attempt_ambiguous(attempt, "timeout")
            mark_attempt_cancelled(attempt, "invalid render")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("attempt_status = 'completed'", sql)
        self.assertIn("attempt_status = 'failed'", sql)
        self.assertIn("attempt_status = 'ambiguous'", sql)
        self.assertIn("attempt_status = 'cancelled'", sql)

    def test_reconcile_records_existing_message_without_sending(self):
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.record_publication_success"
        ) as record, patch("radar_engine.publication.storage.complete_reconcilable_attempt") as complete:
            record.return_value.status = "published"
            reconcile_publication("radar-1", 888, "@vitrinspain", "https://t.me/vitrinspain/888")
        args, kwargs = record.call_args
        self.assertEqual(args[0], "radar-1")
        self.assertEqual(args[1].telegram_message_id, 888)
        self.assertEqual(args[1].channel_post_url, "https://t.me/vitrinspain/888")
        complete.assert_called_once()

    def test_ambiguous_attempt_can_be_reconciled_without_sending(self):
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.record_publication_success"
        ) as record, patch("radar_engine.publication.storage.complete_reconcilable_attempt") as complete:
            record.return_value = type("Result", (), {"status": "published", "published": True})()
            result = reconcile_publication("radar-1", 889, "@vitrinspain", "https://t.me/vitrinspain/889")
        self.assertEqual(result.status, "published")
        self.assertEqual(record.call_args.args[1].telegram_message_id, 889)
        complete.assert_called_once()

    def test_active_sending_cannot_be_released_and_remains_blocking(self):
        cursor = FakeCursor(one=[None, attempt_row(attempt_status="sending")])
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
        ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = release_publication_attempt("radar-1")
        self.assertEqual(result.status, "publication_in_progress")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("FOR UPDATE", sql)
        self.assertNotIn("attempt_status = 'cancelled'", sql)

        cursor = FakeCursor(one=[None, None, attempt_row(attempt_status="sending")])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            claim = claim_publication_attempt("radar-1")
        self.assertTrue(claim.in_progress)
        self.assertEqual(claim.attempt.attempt_status, "sending")

    def test_expired_sending_release_becomes_ambiguous_without_same_call_cancel(self):
        cursor = FakeCursor(one=[attempt_row(attempt_status="ambiguous")])
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
        ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = release_publication_attempt("radar-1")
        self.assertTrue(result.reconciliation_required)
        self.assertIn("manual verification", result.error)
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("attempt_status = 'ambiguous'", sql)
        self.assertIn("expires_at <= CURRENT_TIMESTAMP", sql)
        self.assertNotIn("attempt_status = 'cancelled'", sql)

    def test_second_explicit_release_can_cancel_already_ambiguous_attempt(self):
        cursor = FakeCursor(one=[None, attempt_row(attempt_status="ambiguous"), attempt_row(attempt_status="cancelled")])
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
        ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = release_publication_attempt("radar-1", released_by=123)
        self.assertEqual(result.status, "attempt_released")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("attempt_status = 'cancelled'", sql)
        self.assertIn("released_by = %s", sql)

    def test_release_confirmed_not_sent_allows_later_new_claim(self):
        cursor = FakeCursor(one=[None, attempt_row(attempt_status="ambiguous"), attempt_row(attempt_status="cancelled")])
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
        ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = release_publication_attempt("radar-1", released_by=123)
        self.assertEqual(result.status, "attempt_released")

        cursor = FakeCursor(one=[None, attempt_row(attempt_token="new-token")])
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            claim = claim_publication_attempt("radar-1")
        self.assertTrue(claim.claimed)

    def test_release_action_never_sends_telegram(self):
        cursor = FakeCursor(one=[None, attempt_row(attempt_status="ambiguous"), attempt_row(attempt_status="cancelled")])
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
        ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            release_publication_attempt("radar-1")
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertNotIn("send_message", sql)

    def test_sent_unpersisted_cannot_be_released_as_not_sent(self):
        cursor = FakeCursor(one=[None, attempt_row(attempt_status="sent_unpersisted", telegram_message_id=777)])
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
            "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
        ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            result = release_publication_attempt("radar-1")
        self.assertEqual(result.status, "release_rejected")
        self.assertIn("requires reconciliation", result.error)
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertNotIn("attempt_status = 'cancelled'", sql)

    def test_completed_failed_and_cancelled_attempts_cannot_be_released(self):
        for status in ("completed", "failed", "cancelled"):
            cursor = FakeCursor(one=[None, attempt_row(attempt_status=status)])
            with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value=None), patch(
                "radar_engine.publication.storage.get_radar_item_channel_message", return_value=None
            ), patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
                result = release_publication_attempt("radar-1")
            self.assertEqual(result.status, "release_rejected")
            self.assertIn("cannot be released", result.error)
            sql = "\n".join(statement for statement, _ in cursor.executed)
            self.assertNotIn("attempt_status = 'cancelled'", sql)

    def test_successful_publication_cannot_be_released(self):
        with patch("radar_engine.publication.storage.get_existing_successful_publication", return_value={"id": "pub-1"}):
            result = release_publication_attempt("radar-1")
        self.assertTrue(result.already_published)

    def test_attempt_status_constraint_migration_is_minimally_invasive(self):
        db_text = (PROJECT_ROOT / "database" / "db.py").read_text(encoding="utf-8")
        self.assertIn("pg_get_constraintdef", db_text)
        self.assertIn("current_definition NOT ILIKE '%cancelled%'", db_text)
        self.assertIn("'cancelled'", db_text)

    def test_complete_reconcilable_attempt_does_not_send(self):
        cursor = FakeCursor()
        response = TelegramPublicationResponse("@vitrinspain", 888, "https://t.me/vitrinspain/888")
        with patch.dict(sys.modules, {"database.db": fake_database(cursor)}):
            complete_reconcilable_attempt("radar-1", response)
        sql, params = cursor.executed[0]
        self.assertIn("attempt_status = 'completed'", sql)
        self.assertIn("attempt_status IN ('sent_unpersisted', 'ambiguous')", sql)
        self.assertNotIn("send_message", sql)
        self.assertEqual(params, (888, "@vitrinspain", "https://t.me/vitrinspain/888", "radar-1"))


if __name__ == "__main__":
    unittest.main()
