import unittest

from radar_engine.classification.engine import RadarClassificationEngine
from tests.test_classification_models import make_classification_result, make_classification_source


class ClassificationEngineTests(unittest.TestCase):
    def test_successful_classification_stores_result(self):
        source = make_classification_source()

        class Classifier:
            def classify(self, item):
                return make_classification_result(candidate_id=item.candidate_id)

        stored = []
        engine = RadarClassificationEngine(
            classifier=Classifier(),
            load_candidates=lambda limit, candidate_id=None: [source],
            store_result=lambda result, ai_result_id=None: stored.append((result.candidate_id, ai_result_id)),
        )
        report = engine.run()
        self.assertEqual(report.loaded, 1)
        self.assertEqual(report.processed, 1)
        self.assertEqual(report.completed, 1)
        self.assertEqual(report.failed, 0)
        self.assertEqual(stored, [("candidate-1", "ai-1")])

    def test_one_failure_does_not_stop_next_item(self):
        sources = [
            make_classification_source(candidate_id="bad"),
            make_classification_source(candidate_id="good"),
        ]

        class Classifier:
            def classify(self, item):
                if item.candidate_id == "bad":
                    raise RuntimeError("bad classification")
                return make_classification_result(candidate_id=item.candidate_id)

        stored = []
        engine = RadarClassificationEngine(
            classifier=Classifier(),
            load_candidates=lambda limit, candidate_id=None: sources,
            store_result=lambda result, ai_result_id=None: stored.append(result.candidate_id),
        )
        report = engine.run()
        self.assertEqual(report.loaded, 2)
        self.assertEqual(report.processed, 1)
        self.assertEqual(report.completed, 1)
        self.assertEqual(report.failed, 1)
        self.assertEqual(stored, ["good"])
        self.assertIn("bad", report.errors[0])

    def test_dry_run_does_not_persist(self):
        source = make_classification_source()

        class Classifier:
            def classify(self, item):
                return make_classification_result(candidate_id=item.candidate_id)

        stored = []
        engine = RadarClassificationEngine(
            classifier=Classifier(),
            load_candidates=lambda limit, candidate_id=None: [source],
            store_result=lambda result, ai_result_id=None: stored.append(result.candidate_id),
        )
        report = engine.run(dry_run=True)
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(stored, [])

    def test_existing_results_are_skipped_by_loader_contract(self):
        engine = RadarClassificationEngine(
            classifier=None,
            load_candidates=lambda limit, candidate_id=None: [],
            store_result=lambda result, ai_result_id=None: None,
        )
        report = engine.run()
        self.assertEqual(report.loaded, 0)
        self.assertEqual(report.processed, 0)
        self.assertEqual(report.completed, 0)

    def test_failures_remain_retryable_and_do_not_mutate_candidate_status(self):
        source = make_classification_source()

        class Classifier:
            def classify(self, item):
                raise RuntimeError("temporary")

        writes = []
        engine = RadarClassificationEngine(
            classifier=Classifier(),
            load_candidates=lambda limit, candidate_id=None: [source],
            store_result=lambda result, ai_result_id=None: writes.append("stored"),
        )
        report = engine.run()
        self.assertEqual(report.failed, 1)
        self.assertEqual(writes, [])
        self.assertEqual(source.candidate.candidate_status, "pending_ai")


if __name__ == "__main__":
    unittest.main()
