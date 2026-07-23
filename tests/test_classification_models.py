import unittest

from radar_engine.classification.models import ClassificationSource, RadarClassificationResult
from radar_engine.taxonomy import (
    RADAR_AUDIENCE_VALUES,
    RADAR_CATEGORY_VALUES,
    RADAR_CITY_VALUES,
    RADAR_URGENCY_VALUES,
)
from tests.test_radar_candidate import make_candidate


def make_classification_source(**overrides):
    data = {
        "candidate_id": "candidate-1",
        "ai_result_id": "ai-1",
        "candidate": make_candidate(),
        "ai_headline": "طھغŒطھط±",
        "ai_summary": "ط®ظ„ط§طµظ‡",
        "ai_why_it_matters": "ط¯ظ„غŒظ„ ط§ظ‡ظ…غŒطھ",
    }
    data.update(overrides)
    return ClassificationSource(**data)


def make_classification_result(**overrides):
    data = {
        "candidate_id": "candidate-1",
        "primary_category": "legal",
        "category_tags": ["legal", "legal", "alert"],
        "audience_tags": ["migration", "migration", "all"],
        "cities": ["Madrid", "Madrid"],
        "geographic_scope": "city",
        "urgency": "high",
        "priority_score": 75,
        "confidence": 0.8,
        "model_name": "model",
        "prompt_version": "radar-classification-v1",
        "processing_time_ms": 10,
    }
    data.update(overrides)
    return RadarClassificationResult(**data)


class ClassificationModelTests(unittest.TestCase):
    def test_taxonomy_values_contain_no_mojibake_markers(self):
        values = (
            list(RADAR_CATEGORY_VALUES)
            + list(RADAR_AUDIENCE_VALUES)
            + list(RADAR_CITY_VALUES)
            + list(RADAR_URGENCY_VALUES)
        )
        markers = ("ط", "ظ", "أ،")
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(any(marker in value for marker in markers))

    def test_valid_result_trims_and_deduplicates_lists(self):
        result = make_classification_result(candidate_id=" candidate-1 ")
        self.assertEqual(result.candidate_id, "candidate-1")
        self.assertEqual(result.category_tags, ["legal", "alert"])
        self.assertEqual(result.audience_tags, ["migration", "all"])
        self.assertEqual(result.cities, ["Madrid"])

    def test_rejects_blank_candidate_id(self):
        with self.assertRaises(ValueError):
            make_classification_result(candidate_id=" ")

    def test_rejects_invalid_primary_category(self):
        with self.assertRaises(ValueError):
            make_classification_result(primary_category="unknown-category")

    def test_rejects_invalid_audience(self):
        with self.assertRaises(ValueError):
            make_classification_result(audience_tags=["not-audience"])

    def test_rejects_invalid_city(self):
        with self.assertRaises(ValueError):
            make_classification_result(cities=["Toledo"])

    def test_accepts_malaga_as_utf8_city(self):
        result = make_classification_result(cities=["Málaga"])
        self.assertEqual(result.cities, ["Málaga"])

    def test_rejects_corrupted_city_forms(self):
        corrupted_malaga = "M" + "\u0623\u060c" + "laga"
        corrupted_all_spain = "\u0639\xa9\u0638\u201e \u0637\xa7\u0637\xb3\u0638\xbe\u0637\xa7\u0638\u2020\u063a\u0152\u0637\xa7"
        with self.assertRaises(ValueError):
            make_classification_result(cities=[corrupted_malaga])
        with self.assertRaises(ValueError):
            make_classification_result(cities=[corrupted_all_spain])

    def test_national_scope_accepts_empty_city_list(self):
        result = make_classification_result(geographic_scope="national", cities=[])
        self.assertEqual(result.geographic_scope, "national")
        self.assertEqual(result.cities, [])

    def test_rejects_invalid_geographic_scope(self):
        with self.assertRaises(ValueError):
            make_classification_result(geographic_scope="region")

    def test_rejects_invalid_urgency(self):
        with self.assertRaises(ValueError):
            make_classification_result(urgency="panic")

    def test_rejects_priority_outside_bounds(self):
        with self.assertRaises(ValueError):
            make_classification_result(priority_score=-1)
        with self.assertRaises(ValueError):
            make_classification_result(priority_score=101)

    def test_rejects_confidence_outside_bounds(self):
        with self.assertRaises(ValueError):
            make_classification_result(confidence=-0.1)
        with self.assertRaises(ValueError):
            make_classification_result(confidence=1.1)


if __name__ == "__main__":
    unittest.main()
