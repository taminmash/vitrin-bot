from pathlib import Path
import unittest

from radar_engine.review.callbacks import (
    TELEGRAM_CALLBACK_DATA_LIMIT,
    resolve_review_candidate_token,
    review_callback_data,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RadarReviewCallbackTests(unittest.TestCase):
    def test_compact_review_callbacks_fit_telegram_limit_with_long_candidate_id(self):
        candidate_id = "candidate-" + ("x" * 200)

        for operation in ("i", "a", "x", "e", "p"):
            callback_data = review_callback_data(operation, candidate_id)
            self.assertLessEqual(len(callback_data.encode("utf-8")), TELEGRAM_CALLBACK_DATA_LIMIT)
            self.assertTrue(callback_data.startswith(f"admin_radar:r:{operation}:"))
            token = callback_data.rsplit(":", 1)[1]
            self.assertEqual(resolve_review_candidate_token(token), candidate_id)

    def test_static_review_callbacks_fit_telegram_limit(self):
        for callback_data in ("admin_radar:review:list", "admin_radar:menu:open"):
            self.assertLessEqual(len(callback_data.encode("utf-8")), TELEGRAM_CALLBACK_DATA_LIMIT)

    def test_admin_review_keyboards_use_compact_callbacks(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        queue_helper = admin_text.split("def radar_review_queue_keyboard", 1)[1].split(
            "\n\ndef radar_review_item_text", 1
        )[0]
        item_helper = admin_text.split("def radar_review_item_keyboard", 1)[1].split(
            "\n\ndef radar_promotion_keyboard", 1
        )[0]
        promotion_helper = admin_text.split("def radar_promotion_keyboard", 1)[1].split(
            "\n\nasync def edit_admin_radar_review_queue", 1
        )[0]

        self.assertIn('review_callback_data("i", item.candidate_id)', queue_helper)
        for operation in ("a", "x", "e"):
            self.assertIn(f'review_callback_data("{operation}", candidate_id)', item_helper)
        self.assertIn('review_callback_data("p", candidate_id)', promotion_helper)
        self.assertNotIn("admin_radar:review:item:{item.candidate_id}", queue_helper)
        self.assertNotIn("admin_radar:review:needs_edit:{candidate_id}", item_helper)
        self.assertNotIn("admin_radar:promote:{candidate_id}", promotion_helper)

    def test_compact_review_handler_resolves_server_side_token(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        compact_branch = admin_text.split('if action == "r":', 1)[1].split('\n    if action == "menu":', 1)[0]

        self.assertIn("resolve_review_candidate_token(token)", compact_branch)
        self.assertIn('"i": "item"', compact_branch)
        self.assertIn('"a": "approve"', compact_branch)
        self.assertIn('"x": "reject"', compact_branch)
        self.assertIn('"e": "needs_edit"', compact_branch)
        self.assertIn('"p": "promote"', compact_branch)
        self.assertIn('parts = ["admin_radar", "promote", candidate_id]', compact_branch)


if __name__ == "__main__":
    unittest.main()
