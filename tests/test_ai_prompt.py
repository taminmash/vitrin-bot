import unittest

from radar_engine.ai.prompts import PROMPT_VERSION, build_summary_prompt
from tests.test_radar_candidate import make_candidate


class AIPromptTests(unittest.TestCase):
    def test_prompt_is_versioned_and_constrained(self):
        messages = build_summary_prompt(make_candidate(title="Titulo", body="Texto oficial en español."))
        self.assertEqual(PROMPT_VERSION, "radar-structured-v5")
        combined = "\n".join(message["content"] for message in messages)
        self.assertIn("factual", combined)
        self.assertIn("Do not hallucinate", combined)
        self.assertIn("legal interpretation", combined)
        self.assertIn("Spanish", combined)
        self.assertIn("Persian", combined)
        self.assertIn("requirements", combined)
        self.assertIn("salary", combined)
        self.assertIn("job_title", combined)
        self.assertIn("job_title_confidence", combined)
        self.assertIn("at most 6 words", combined)
        self.assertIn('"UNKNOWN"', combined)
        self.assertIn("job_title_extraction_needed: NO", combined)
        self.assertIn("visa_sponsorship", combined)
        self.assertIn("visa_sponsorship_evidence", combined)
        self.assertIn("verbatim excerpt", combined)
        self.assertIn("probable/possible support are not visa sponsorship", combined)
        self.assertIn("apply_from_outside_spain", combined)
        self.assertIn("why_it_matters", combined)
        self.assertIn("full_text_fa", combined)
        self.assertIn("full_persian_translation_needed: YES", combined)

    def test_non_boe_source_does_not_request_full_translation(self):
        candidate = make_candidate(source_key="madrid_empleo", source_name="Madrid Empleo")
        combined = "\n".join(message["content"] for message in build_summary_prompt(candidate))
        self.assertIn("full_persian_translation_needed: NO", combined)

    def test_generic_source_title_requests_profession_extraction(self):
        messages = build_summary_prompt(make_candidate(title="una plaza", body="Auxiliar Administrativo"))
        combined = "\n".join(message["content"] for message in messages)
        self.assertIn("job_title_extraction_needed: YES", combined)
