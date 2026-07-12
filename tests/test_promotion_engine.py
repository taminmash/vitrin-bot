import unittest

from radar_engine.promotion.engine import RadarPromotionEngine
from radar_engine.promotion.models import PromotionResult
from tests.test_promotion_mapper import make_source


class PromotionEngineTests(unittest.TestCase):
    def test_successful_promotion_and_dry_run(self):
        source = make_source()
        promoted = []

        def promote(item, promoted_by=None):
            promoted.append((item.candidate_id, promoted_by))
            return PromotionResult(item.candidate_id, "created", radar_item_id="radar-1")

        report = RadarPromotionEngine(loader=lambda **kwargs: [source], promoter=promote).run(promoted_by=123)
        self.assertEqual(report.loaded, 1)
        self.assertEqual(report.processed, 1)
        self.assertEqual(report.created, 1)
        self.assertEqual(promoted, [("candidate-1", 123)])

        dry_report = RadarPromotionEngine(loader=lambda **kwargs: [source], promoter=promote).run(dry_run=True)
        self.assertEqual(dry_report.created, 1)

    def test_already_promoted_and_validation_rejection(self):
        promoted = make_source(already_promoted=True, promotion_id="p1", radar_item_id="r1")
        invalid = make_source()
        invalid.summary.summary = ""
        report = RadarPromotionEngine(loader=lambda **kwargs: [promoted, invalid]).run()
        self.assertEqual(report.already_promoted, 1)
        self.assertEqual(report.rejected, 1)
        self.assertEqual(report.failed, 0)

    def test_one_failure_does_not_stop_next_item_and_limit_is_honored(self):
        calls = []

        def loader(**kwargs):
            calls.append(kwargs["limit"])
            return [make_source(candidate_id="bad"), make_source(candidate_id="good")]

        def promote(source, promoted_by=None):
            if source.candidate_id == "bad":
                raise RuntimeError("store failed")
            return PromotionResult(source.candidate_id, "created", radar_item_id="radar-2")

        report = RadarPromotionEngine(loader=loader, promoter=promote).run(limit=999)
        self.assertEqual(calls, [200])
        self.assertEqual(report.processed, 2)
        self.assertEqual(report.created, 1)
        self.assertEqual(report.failed, 1)


if __name__ == "__main__":
    unittest.main()

