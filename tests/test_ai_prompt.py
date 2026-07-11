import unittest

from radar_engine.ai.prompts import PROMPT_VERSION, build_summary_prompt
from tests.test_radar_candidate import make_candidate


class AIPromptTests(unittest.TestCase):
    def test_prompt_is_versioned_and_constrained(self):
        messages = build_summary_prompt(make_candidate(title="Titulo", body="Texto oficial en español."))
        self.assertEqual(PROMPT_VERSION, "radar-summary-v1")
        combined = "\n".join(message["content"] for message in messages)
        self.assertIn("factual", combined)
        self.assertIn("Do not hallucinate", combined)
        self.assertIn("legal interpretation", combined)
        self.assertIn("Spanish", combined)
        self.assertIn("Persian", combined)
        self.assertIn("headline", combined)
        self.assertIn("short_summary", combined)
        self.assertIn("why_it_matters", combined)
