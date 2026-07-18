import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HAS_TELEGRAM = importlib.util.find_spec("telegram") is not None


class PublicationAdminStaticTests(unittest.TestCase):
    def test_admin_publish_uses_explicit_confirmation_and_engine(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        self.assertIn("admin_radar:publish_confirm:", admin_text)
        self.assertIn("RadarPublicationEngine", admin_text)
        self.assertIn("RadarTelegramPublisher", admin_text)
        self.assertIn("EligiblePublicationItem(item)", admin_text)

    def test_old_direct_publish_helper_no_longer_calls_telegram_directly(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        helper = admin_text.split("async def publish_radar_item", 1)[1].split("\n\n", 1)[0]
        self.assertIn("RadarPublicationEngine", helper)
        self.assertNotIn("send_message", helper)
        self.assertNotIn("mark_radar_channel_published", helper)

    def test_admin_preserves_structured_publication_statuses(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        result_helper = admin_text.split("async def edit_radar_publication_result", 1)[1].split(
            "\n\ndef radar_admin_list_text", 1
        )[0]
        self.assertIn("result.in_progress", result_helper)
        self.assertIn("result.reconciliation_required", result_helper)
        self.assertIn("result.already_published", result_helper)
        self.assertIn("result.published", result_helper)

    def test_admin_no_longer_calls_generic_failure_mutation_for_publication_results(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        self.assertNotIn("mark_radar_channel_failed", admin_text)
        self.assertIn("publication_in_progress", (PROJECT_ROOT / "radar_engine" / "publication" / "models.py").read_text(encoding="utf-8"))

    def test_admin_ready_payload_is_not_pre_marked_public(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        payload_helper = admin_text.split("def create_payload_from_radar_data", 1)[1].split(
            "\n\nasync def publish_radar_item", 1
        )[0]
        self.assertIn('"is_published": status == "published"', payload_helper)
        self.assertNotIn('"is_published": status in ("ready", "published")', payload_helper)

    def test_direct_approval_flow_and_navigation_labels_are_present(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        self.assertIn('InlineKeyboardButton("✅ انتشار در ویترین"', admin_text)
        self.assertIn('InlineKeyboardButton("⏳ انتقال به انتظار انتشار"', admin_text)
        self.assertIn('safe_review_callback_data("u", candidate_id)', admin_text)
        self.assertIn('safe_review_callback_data("p", candidate_id)', admin_text)
        self.assertIn('publish_radar_item(context, item, published_by=query.from_user.id)', admin_text)
        self.assertIn("BACK_BUTTON", admin_text)
        self.assertIn("HOME_BUTTON", admin_text)
        for forbidden in (
            'InlineKeyboardButton("⬅️ بازگشت',
            'InlineKeyboardButton("↩️ بازگشت',
            'InlineKeyboardButton("🏠 خانه"',
            'InlineKeyboardButton("🏠 بازگشت',
            'InlineKeyboardButton("بازگشت"',
        ):
            self.assertNotIn(forbidden, admin_text)


if __name__ == "__main__":
    unittest.main()
