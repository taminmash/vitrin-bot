import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
import os
from unittest.mock import patch
from zoneinfo import ZoneInfo

from radar_engine.job_expiration import (
    EXPIRED_DETAIL_MESSAGE,
    EXPIRED_PUBLICATION_MESSAGE,
    MADRID_TZ,
    job_temporal_state,
    expired_channel_edit_enabled,
    parse_source_datetime,
    refresh_expired_jobs,
    ExpirationRefreshReport,
)
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.pipeline.validator import validate_candidate
from radar_engine.publication.publisher import validate_publication_item
from radar_engine.renderer import render_channel_post, render_details_page
from radar_engine.scheduler import RadarBOEIngestionScheduler, _default_expiration_stage
from tests.test_publication_publisher import ready_item
from tests.test_radar_candidate import make_candidate


def job_item(**overrides):
    item = {
        "id": "job-1",
        "type": "job",
        "title": "مهندس نرم افزار",
        "summary": "خلاصه",
        "content_status": "ready",
        "channel_status": "not_sent",
        "is_published": False,
        "channel_message_id": None,
        "structured_data": {"category": "job", "job_title": "مهندس نرم افزار"},
    }
    item.update(overrides)
    return item


class JobExpirationPolicyTests(unittest.TestCase):
    def test_channel_edit_is_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(expired_channel_edit_enabled())
    def test_structured_dates_have_priority_and_publication_is_not_deadline(self):
        item = job_item(
            published_at=datetime(2026, 7, 1),
            expires_at=datetime(2026, 8, 1),
            structured_data={
                "category": "job", "job_title": "مهندس",
                "publication_date": "2026-07-02", "deadline": "2026-07-30",
            },
        )
        state = job_temporal_state(item, now=datetime(2026, 7, 10, 12, tzinfo=MADRID_TZ))
        self.assertEqual(state.publication_date.date().isoformat(), "2026-07-02")
        self.assertEqual(state.deadline.date().isoformat(), "2026-07-30")
        no_deadline = job_temporal_state(
            job_item(structured_data={"category": "job", "publication_date": "2026-07-02"}),
            now=datetime(2026, 7, 10, tzinfo=MADRID_TZ),
        )
        self.assertTrue(no_deadline.deadline_unknown)
        self.assertFalse(no_deadline.expired)

    def test_deadline_later_today_is_active_but_yesterday_is_expired(self):
        now = datetime(2026, 7, 18, 10, tzinfo=MADRID_TZ)
        later = job_temporal_state(job_item(structured_data={"deadline": "2026-07-18"}), now=now)
        yesterday = job_temporal_state(job_item(structured_data={"deadline": "2026-07-17"}), now=now)
        self.assertFalse(later.expired)
        self.assertEqual(later.days_remaining, 0)
        self.assertTrue(yesterday.expired)

    def test_official_closed_status_expires_without_deadline(self):
        state = job_temporal_state(job_item(structured_data={"source_status": "plazo cerrado"}))
        self.assertTrue(state.expired)
        self.assertEqual(state.expiration_reason, "source_status:plazo cerrado")

    def test_madrid_timezone_and_daylight_saving_boundaries(self):
        winter = parse_source_datetime("2026-01-15T12:00:00Z")
        summer = parse_source_datetime("2026-07-15T12:00:00Z")
        self.assertEqual(winter.utcoffset(), timedelta(hours=1))
        self.assertEqual(summer.utcoffset(), timedelta(hours=2))

    def test_stale_without_deadline_is_not_expired(self):
        state = job_temporal_state(
            job_item(published_at=datetime(2026, 5, 1)),
            now=datetime(2026, 7, 18, tzinfo=MADRID_TZ),
            stale_days=30,
        )
        self.assertTrue(state.stale)
        self.assertFalse(state.expired)
        self.assertTrue(state.deadline_unknown)

    def test_expired_candidate_is_rejected_before_ai_review(self):
        candidate = make_candidate(
            title="Auxiliar Administrativo",
            body="Convocatoria oficial con información suficiente para participar.",
            source_category="jobs",
            metadata={"content_type": "job", "is_expired": True},
        )
        result = validate_candidate(candidate)
        self.assertFalse(result.is_valid)
        self.assertIn("expired", {issue.code for issue in result.issues})

    def test_expiration_rechecked_before_telegram_send(self):
        item = ready_item(type="job", structured_data={"deadline": "2020-01-01"}, expires_at=None)
        errors = validate_publication_item(item, rendered_text="post", channel_id="@vitrin")
        expired = next(error for error in errors if error["code"] == "expired")
        self.assertEqual(expired["message"], EXPIRED_PUBLICATION_MESSAGE)

    def test_expired_detail_remains_visible_and_non_actionable(self):
        item = job_item(structured_data={"category": "job", "job_title": "معمار", "deadline": "2020-01-01"})
        text = render_details_page(item)
        self.assertTrue(text.startswith(EXPIRED_DETAIL_MESSAGE))
        self.assertIn("معمار", text)
        self.assertNotIn("نیاز به کمک برای ارسال درخواست", text)

    def test_active_overview_hides_dates_while_detail_keeps_deadline_warning(self):
        now = datetime.now(MADRID_TZ)
        deadline = now + timedelta(days=2)
        item = job_item(
            structured_data={
                "category": "job", "job_title": "معمار",
                "publication_date": now.date().isoformat(), "deadline": deadline.date().isoformat(),
            }
        )
        channel = render_channel_post(item)
        detail = render_details_page(item)
        self.assertNotIn("📅 تاریخ انتشار", channel)
        self.assertNotIn("مهلت ارسال درخواست", channel)
        self.assertIn("📅 مهلت ارسال درخواست", detail)
        self.assertIn("⚠️ تنها 2 روز تا پایان مهلت", detail)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executions = []
        self.rowcount = 0

    def execute(self, sql, params=()):
        self.executions.append((sql, params))
        self.rowcount = 1 if sql.lstrip().startswith("UPDATE") else 0

    def fetchall(self):
        return self.rows


class ExpirationRefreshTests(unittest.TestCase):
    def test_refresh_is_bounded_idempotent_and_never_deletes_history(self):
        rows = [job_item(id="expired-1", structured_data={"deadline": "2020-01-01"})]
        cursor = FakeCursor(rows)

        @contextmanager
        def fake_cursor(**kwargs):
            yield None, cursor

        with patch("database.db.db_cursor", fake_cursor):
            report = refresh_expired_jobs(limit=25)
        sql = "\n".join(statement for statement, _ in cursor.executions)
        self.assertEqual(report.expired, 1)
        self.assertIn("LIMIT %s", sql)
        self.assertNotIn("DELETE", sql.upper())
        self.assertIn("content_status = 'expired'", sql)


class SchedulerExpirationTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_refreshes_expiration_once_inside_normal_cycle(self):
        calls = []

        async def expiration_stage():
            calls.append("expiration")
            return ExpirationRefreshReport(evaluated=2, expired=1, stale=1)

        async def noop_stage():
            return None

        @contextmanager
        def lock():
            yield True

        scheduler = RadarBOEIngestionScheduler(
            ingest_stage=noop_stage,
            pipeline_stage=noop_stage,
            actionability_backfill_stage=noop_stage,
            ai_stage=noop_stage,
            classification_stage=noop_stage,
            urgent_publication_stage=noop_stage,
            expiration_stage=expiration_stage,
            lock_factory=lock,
        )
        report = await scheduler.run_once()
        self.assertEqual(calls, ["expiration"])
        self.assertEqual(report.jobs_expired_refreshed, 1)
        self.assertEqual(report.stale_jobs_flagged, 1)

    async def test_optional_channel_edit_is_best_effort_and_does_not_rollback_expiration(self):
        class FailingBot:
            async def edit_message_text(self, **kwargs):
                raise RuntimeError("Telegram edit failed")

        expired = job_item(id="published-expired", channel_message_id=123, structured_data={"deadline": "2020-01-01"})
        report = ExpirationRefreshReport(evaluated=1, expired=1, expired_items=(expired,))
        with patch.dict(os.environ, {"RADAR_EXPIRED_CHANNEL_EDIT_ENABLED": "true"}), patch(
            "radar_engine.job_expiration.refresh_expired_jobs", return_value=report
        ):
            result = await _default_expiration_stage(FailingBot())
        self.assertEqual(result.expired, 1)


if __name__ == "__main__":
    unittest.main()
