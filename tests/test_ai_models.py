import unittest

from radar_engine.ai.models import AITaskResult


class AITaskResultTests(unittest.TestCase):
    def test_valid_result_trims_and_casts(self):
        result = AITaskResult(
            headline=" تیتر ",
            short_summary=" خلاصه ",
            why_it_matters=" دلیل ",
            confidence="0.75",
            model_name=" gpt-test ",
            prompt_version=" radar-summary-v1 ",
            processing_time_ms="42",
        )
        self.assertEqual(result.headline, "تیتر")
        self.assertEqual(result.confidence, 0.75)
        self.assertEqual(result.processing_time_ms, 42)

    def test_rejects_blank_fields_and_invalid_confidence(self):
        with self.assertRaises(ValueError):
            AITaskResult("", "summary", "why", 0.5, "model", "prompt", 1)
        with self.assertRaises(ValueError):
            AITaskResult("headline", "summary", "why", 1.5, "model", "prompt", 1)

    def test_why_it_matters_may_be_empty(self):
        result = AITaskResult("headline", "summary", None, 0.5, "model", "prompt", 1)
        self.assertEqual(result.why_it_matters, "")
