import unittest

from radar_engine.ai.summarizer import RadarAISummarizer
from radar_engine.job_title import UNKNOWN_JOB_TITLE, displayed_job_title, existing_job_title, valid_ai_job_title
from radar_engine.job_presentation import job_card
from tests.test_radar_candidate import make_candidate


class JobTitleSelectionTests(unittest.TestCase):
    def test_existing_meaningful_title_wins(self):
        self.assertEqual(
            displayed_job_title("مهندس نرم افزار", {"occupation": "معمار"}, "کارشناس شبکه", 0.99),
            "مهندس نرم افزار",
        )
        self.assertEqual(existing_job_title("مهندس نرم افزار", {"occupation": "معمار"}), "مهندس نرم افزار")

    def test_structured_occupation_wins_when_source_title_is_generic(self):
        self.assertEqual(
            displayed_job_title("استخدام برای یک موقعیت شغلی", {"occupation": "معمار شهرداری"}, "مهندس عمران", 0.99),
            "معمار شهرداری",
        )

    def test_high_confidence_persian_ai_extraction_is_used(self):
        self.assertEqual(
            displayed_job_title("Convocatoria Técnico Informático", {}, "کارشناس فناوری اطلاعات", 0.91),
            "کارشناس فناوری اطلاعات",
        )

    def test_unknown_or_generic_ai_profession_uses_fallback(self):
        for title in ("UNKNOWN", "فرصت شغلی", "استخدام", "یک موقعیت شغلی"):
            with self.subTest(title=title):
                self.assertEqual(displayed_job_title("puesto", {}, title, 0.99), UNKNOWN_JOB_TITLE)

    def test_ai_title_requires_confidence_threshold(self):
        self.assertEqual(displayed_job_title("una plaza", {}, "دستیار اداری", 0.849), UNKNOWN_JOB_TITLE)
        self.assertEqual(displayed_job_title("una plaza", {}, "دستیار اداری", 0.85), "دستیار اداری")

    def test_ai_title_must_be_persian_without_punctuation(self):
        self.assertIsNone(valid_ai_job_title("Arquitecto Municipal", 0.99))
        self.assertIsNone(valid_ai_job_title("معمار شهرداری!", 0.99))
        self.assertEqual(valid_ai_job_title("معمار شهرداری", 0.99), "معمار شهرداری")

    def test_ai_title_has_six_word_maximum(self):
        self.assertEqual(valid_ai_job_title("کارشناس ارشد فناوری اطلاعات شبکه سازمانی", 0.99), "کارشناس ارشد فناوری اطلاعات شبکه سازمانی")
        self.assertIsNone(valid_ai_job_title("کارشناس ارشد فناوری اطلاعات شبکه سازمانی شهرداری", 0.99))

    def test_summarizer_uses_ai_extraction_without_an_extra_request(self):
        class Client:
            model = "test-model"

            def __init__(self):
                self.calls = 0

            def complete_json(self, messages, schema=None):
                self.calls += 1
                return {
                    "category": "job",
                    "job_title": "دستیار اداری",
                    "job_title_confidence": 0.92,
                    "why_it_matters": None,
                    "confidence": 0.9,
                }

        client = Client()
        candidate = make_candidate(
            title="Resolución para una plaza",
            body="Resolución para cubrir una plaza de Auxiliar Administrativo",
            source_category="jobs",
        )
        result = RadarAISummarizer(client).summarize(candidate)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result.structured_data["job_title"], "دستیار اداری")
        self.assertEqual(result.headline, "دستیار اداری")

    def test_legacy_generic_structured_title_is_not_displayed(self):
        text = job_card({"category": "job", "job_title": "استخدام برای یک موقعیت شغلی"})
        self.assertIn(f"💼 عنوان شغل\n{UNKNOWN_JOB_TITLE}", text)
        self.assertNotIn("استخدام برای یک موقعیت شغلی", text)


if __name__ == "__main__":
    unittest.main()
