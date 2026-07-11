import unittest

from radar_engine.review.engine import RadarReviewEngine
from radar_engine.review.models import ReviewQueueReport
from tests.test_review_storage import queue_row
from radar_engine.review.storage import _row_to_queue_item


class ReviewEngineTests(unittest.TestCase):
    def test_queue_report_uses_status_counts(self):
        report = ReviewQueueReport(pending=7, approved=2, rejected=1, needs_edit=3)
        engine = RadarReviewEngine(
            load_queue=lambda limit, candidate_id=None: [_row_to_queue_item(queue_row())],
            status_report=lambda: report,
        )
        result = engine.queue_report(limit=10)
        self.assertEqual(result.pending, 7)
        self.assertEqual(result.approved, 2)
        self.assertEqual(result.rejected, 1)
        self.assertEqual(result.needs_edit, 3)

    def test_candidate_specific_report_uses_loaded_queue_length(self):
        report = ReviewQueueReport(pending=7)
        engine = RadarReviewEngine(
            load_queue=lambda limit, candidate_id=None: [_row_to_queue_item(queue_row())],
            status_report=lambda: report,
        )
        result = engine.queue_report(candidate_id="candidate-1")
        self.assertEqual(result.pending, 1)


if __name__ == "__main__":
    unittest.main()
