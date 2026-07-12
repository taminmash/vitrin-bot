import unittest

from radar_engine.promotion.models import MappedRadarItemPayload, PromotionResult, validate_promotion_status


class PromotionModelTests(unittest.TestCase):
    def test_valid_status_and_payload(self):
        self.assertEqual(validate_promotion_status("completed"), "completed")
        payload = MappedRadarItemPayload(
            fields={
                "title": "Headline",
                "summary": "Summary",
                "type": "legal",
                "source_url": "https://boe.es/test",
                "source_name": "BOE",
            }
        )
        self.assertEqual(payload.content_status, "ready")

    def test_invalid_status_is_rejected_but_blank_fields_reach_validator(self):
        with self.assertRaises(ValueError):
            validate_promotion_status("ready")
        payload = MappedRadarItemPayload(fields={"title": "", "summary": "s", "type": "legal", "source_url": "u"})
        self.assertEqual(payload.fields["title"], "")

    def test_result_flags(self):
        self.assertTrue(PromotionResult("c1", "created").created)
        self.assertTrue(PromotionResult("c1", "already_promoted").already_promoted)


if __name__ == "__main__":
    unittest.main()
