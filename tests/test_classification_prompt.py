import unittest

from radar_engine.classification.prompts import PROMPT_VERSION, build_classification_prompt
from radar_engine.taxonomy import (
    RADAR_AUDIENCE_VALUES,
    RADAR_CATEGORY_VALUES,
    RADAR_CITY_VALUES,
    RADAR_URGENCY_VALUES,
)
from tests.test_classification_models import make_classification_source


class ClassificationPromptTests(unittest.TestCase):
    def test_prompt_is_versioned_and_contains_required_context(self):
        source = make_classification_source()
        messages = build_classification_prompt(source)
        text = "\n".join(message["content"] for message in messages)
        self.assertEqual(PROMPT_VERSION, "radar-classification-v1")
        self.assertIn("radar-classification-v1", text)
        self.assertIn(source.candidate.title, text)
        self.assertIn(source.candidate.body, text)
        self.assertIn(source.ai_headline, text)
        self.assertIn(source.ai_summary, text)
        self.assertIn(source.ai_why_it_matters, text)
        self.assertIn("structured JSON only", text)
        self.assertIn("Do not invent facts", text)
        self.assertIn("Do not reinterpret laws", text)
        self.assertIn("Málaga", text)
        self.assertNotIn("M" + "\u0623\u060c" + "laga", text)
        self.assertIn("Use national scope when the content clearly applies across Spain", text)
        for value in RADAR_CATEGORY_VALUES:
            self.assertIn(value, text)
        for value in RADAR_AUDIENCE_VALUES:
            self.assertIn(value, text)
        for value in RADAR_CITY_VALUES:
            self.assertIn(value, text)
        for value in RADAR_URGENCY_VALUES:
            self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
