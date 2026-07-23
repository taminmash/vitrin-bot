from pathlib import Path
import importlib
import unittest

from radar_engine.review import callbacks
from radar_engine.review.callbacks import (
    TELEGRAM_CALLBACK_DATA_LIMIT,
    review_callback_byte_length,
    review_callback_data,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_CANDIDATE_ID = "123e4567-e89b-12d3-a456-426614174000"


class RadarReviewCallbackTests(unittest.TestCase):
    def test_compact_review_callbacks_fit_telegram_limit_with_real_uuid_candidate_id(self):
        expected_formats = {
            "i": f"admin_radar:r:i:{REAL_CANDIDATE_ID}",
            "a": f"admin_radar:r:a:{REAL_CANDIDATE_ID}",
            "x": f"admin_radar:r:x:{REAL_CANDIDATE_ID}",
            "e": f"admin_radar:r:e:{REAL_CANDIDATE_ID}",
            "p": f"admin_radar:r:p:{REAL_CANDIDATE_ID}",
            "u": f"admin_radar:r:u:{REAL_CANDIDATE_ID}",
            "d": f"admin_radar:r:d:{REAL_CANDIDATE_ID}",
        }

        for operation, expected in expected_formats.items():
            with self.subTest(operation=operation):
                callback_data = review_callback_data(operation, REAL_CANDIDATE_ID)
                self.assertEqual(callback_data, expected)
                self.assertLessEqual(len(callback_data.encode("utf-8")), TELEGRAM_CALLBACK_DATA_LIMIT)
                self.assertEqual(review_callback_byte_length(operation, REAL_CANDIDATE_ID), 52)

    def test_candidate_id_resolves_directly_after_process_restart_simulation(self):
        callback_data = review_callback_data("a", REAL_CANDIDATE_ID)
        importlib.reload(callbacks)

        parts = callback_data.split(":")
        self.assertEqual(parts[:3], ["admin_radar", "r", "a"])
        self.assertEqual(parts[3], REAL_CANDIDATE_ID)

    def test_no_global_token_registry_exists(self):
        self.assertFalse(hasattr(callbacks, "REVIEW_CALLBACK_CANDIDATES"))
        self.assertFalse(hasattr(callbacks, "review_candidate_token"))
        self.assertFalse(hasattr(callbacks, "resolve_review_candidate_token"))

    def test_static_review_callbacks_fit_telegram_limit(self):
        for callback_data in ("admin_radar:review:list", "admin_radar:menu:open"):
            self.assertLessEqual(len(callback_data.encode("utf-8")), TELEGRAM_CALLBACK_DATA_LIMIT)

    def test_admin_review_keyboards_use_direct_compact_callbacks(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        queue_helper = admin_text.split("def radar_review_queue_keyboard", 1)[1].split(
            "\n\ndef radar_review_item_text", 1
        )[0]
        item_helper = admin_text.split("def radar_review_item_keyboard", 1)[1].split(
            "\n\ndef approved_radar_decision_keyboard", 1
        )[0]
        promotion_helper = admin_text.split("def approved_radar_decision_keyboard", 1)[1].split(
            "\n\ndef safe_review_callback_data", 1
        )[0]

        self.assertIn('safe_review_callback_data("i", item.candidate_id)', queue_helper)
        for operation in ("a", "x", "e"):
            self.assertIn(f'"{operation}"', item_helper)
        self.assertIn("safe_review_callback_data(operation, candidate_id)", item_helper)
        self.assertIn('safe_review_callback_data("p", candidate_id)', promotion_helper)
        self.assertIn('safe_review_callback_data("u", candidate_id)', promotion_helper)
        self.assertNotIn("admin_radar:review:item:{item.candidate_id}", queue_helper)
        self.assertNotIn("admin_radar:review:needs_edit:{candidate_id}", item_helper)
        self.assertNotIn("admin_radar:promote:{candidate_id}", promotion_helper)

    def test_compact_review_handler_uses_candidate_id_without_memory_lookup(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        compact_branch = admin_text.split('if action == "r":', 1)[1].split('\n    if action == "menu":', 1)[0]

        self.assertIn('candidate_id = parts[3] if len(parts) > 3 else ""', compact_branch)
        self.assertNotIn("resolve_review_candidate_token", compact_branch)
        self.assertIn('"i": "item"', compact_branch)
        self.assertIn('"a": "approve"', compact_branch)
        self.assertIn('"x": "reject"', compact_branch)
        self.assertIn('"e": "needs_edit"', compact_branch)
        self.assertIn('"p": "promote"', compact_branch)
        self.assertIn('"u": "publish_approved"', compact_branch)
        self.assertIn('parts = ["admin_radar", operation, candidate_id]', compact_branch)

    def test_legacy_callbacks_remain_supported(self):
        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        review_branch = admin_text.split('if action == "review":', 1)[1].split('\n    if action == "approved_decision":', 1)[0]

        self.assertIn('operation = parts[2] if len(parts) > 2 else "list"', review_branch)
        self.assertIn('candidate_id = parts[3] if len(parts) > 3 else None', review_branch)
        self.assertIn('if operation == "item" and candidate_id:', review_branch)
        self.assertIn('if operation in ("approve", "reject", "needs_edit") and candidate_id:', review_branch)

    def test_invalid_oversized_candidate_id_fails_before_telegram_receives_callback(self):
        oversized_candidate_id = "candidate-" + ("x" * 200)
        with self.assertRaises(ValueError):
            review_callback_data("i", oversized_candidate_id)

        admin_text = (PROJECT_ROOT / "handlers" / "admin.py").read_text(encoding="utf-8")
        safe_helper = admin_text.split("def safe_review_callback_data", 1)[1].split(
            "\n\nasync def edit_admin_radar_review_queue", 1
        )[0]

        self.assertIn("except ValueError:", safe_helper)
        self.assertIn("logger.error(", safe_helper)
        self.assertIn("return None", safe_helper)


if __name__ == "__main__":
    unittest.main()
