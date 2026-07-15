from pathlib import Path
from unittest.mock import patch
import re
import types
import unittest

from radar_engine.status import build_radar_status_text, collect_runtime_status, scheduler_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RadarStatusTextTests(unittest.TestCase):
    def test_build_status_text_includes_all_requested_sections(self):
        text = build_radar_status_text(
            metrics={
                "boe_last_fetch_time": "2026-07-15 10:30:00",
                "boe_last_fetch_result": "inserted",
                "pending_ai": 3,
                "ai_completed": 7,
                "pending_review": 2,
                "approved": 1,
                "published": 4,
                "ai_queue_size": 3,
            },
            scheduler="Running",
            provider={"provider": "gemini", "model": "gemini-2.5-flash-lite"},
            queue={"batch_limit": 1, "delay_seconds": 15.0},
            current_time="2026-07-15T08:30:00+00:00",
            bot_version="abc123",
        )

        for expected in (
            "========================",
            "Radar Status",
            "Scheduler:",
            "- Running",
            "AI Provider:",
            "- Provider: gemini",
            "- Model: gemini-2.5-flash-lite",
            "BOE:",
            "- Last fetch time: 2026-07-15 10:30:00",
            "- Last fetch result: inserted",
            "Candidates:",
            "- Pending AI: 3",
            "- AI completed: 7",
            "- Pending review: 2",
            "- Approved: 1",
            "- Published: 4",
            "AI Queue:",
            "- Current queue size: 3",
            "- Batch limit: 1",
            "- Delay seconds: 15.0",
            "System:",
            "- Current UTC time: 2026-07-15T08:30:00+00:00",
            "- Bot version: abc123",
        ):
            self.assertIn(expected, text)

    def test_unknown_is_used_for_unavailable_values(self):
        text = build_radar_status_text(metrics=None)
        self.assertIn("- Unknown", text)
        self.assertIn("- Provider: Unknown", text)
        self.assertIn("- Current queue size: Unknown", text)

    def test_scheduler_running_and_unknown(self):
        running_task = types.SimpleNamespace(done=lambda: False)
        app = types.SimpleNamespace(
            bot_data={"radar_boe_scheduler": object(), "radar_boe_scheduler_task": running_task}
        )
        self.assertEqual(scheduler_status(app), "Running")
        self.assertEqual(scheduler_status(types.SimpleNamespace(bot_data={})), "Unknown")

    def test_collect_runtime_status_uses_runtime_inputs_without_database(self):
        metrics = {"pending_ai": 5, "ai_queue_size": 5}
        with patch("radar_engine.status.provider_info") as provider_info, patch(
            "radar_engine.status.git_commit_version", return_value="commit123"
        ), patch("radar_engine.status.current_utc_time", return_value="now"):
            provider_info.return_value = types.SimpleNamespace(provider="gemini", model="gemini-2.5-flash-lite")
            text = collect_runtime_status(None, metrics=metrics)

        self.assertIn("- Provider: gemini", text)
        self.assertIn("- Current queue size: 5", text)
        self.assertIn("- Bot version: commit123", text)


class RadarStatusIntegrationSourceTests(unittest.TestCase):
    def test_bot_registers_radar_status_command(self):
        bot_text = (PROJECT_ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn('CommandHandler("radar_status", radar_status_command)', bot_text)

    def test_admin_command_checks_admin_before_loading_metrics(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        helper = admin_text.split("async def radar_status_command", 1)[1].split(
            "\n\nasync def show_pending_admin_items", 1
        )[0]
        self.assertLess(helper.index("is_admin"), helper.index("get_radar_status_metrics"))

    def test_status_metrics_helper_is_read_only(self):
        db_text = (PROJECT_ROOT / "database" / "db.py").read_text(encoding="utf-8")
        helper = db_text.split("def get_radar_status_metrics", 1)[1].split("\n\ndef radar_content_status", 1)[0]
        upper = helper.upper()
        self.assertIn("SELECT", upper)
        self.assertIsNone(re.search(r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b", upper))


if __name__ == "__main__":
    unittest.main()
