import unittest

from radar_engine.review.models import RadarReviewDecision, validate_review_status


class ReviewModelTests(unittest.TestCase):
    def test_valid_statuses_are_accepted(self):
        for status in ("pending", "approved", "rejected", "needs_edit"):
            self.assertEqual(validate_review_status(status), status)

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_review_status("published")

    def test_decision_rejects_pending_and_blank_candidate(self):
        with self.assertRaises(ValueError):
            RadarReviewDecision("candidate-1", "pending")
        with self.assertRaises(ValueError):
            RadarReviewDecision(" ", "approved")


if __name__ == "__main__":
    unittest.main()
