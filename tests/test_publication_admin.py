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


if __name__ == "__main__":
    unittest.main()
