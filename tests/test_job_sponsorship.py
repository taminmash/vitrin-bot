import unittest

from radar_engine.job_sponsorship import (
    apply_sponsorship_verification,
    evidence_matches_original,
    has_verified_sponsorship,
    normalize_sponsorship_value,
)


class JobSponsorshipTests(unittest.TestCase):
    def test_explicit_yes_requires_verbatim_original_evidence(self):
        structured = apply_sponsorship_verification(
            {
                "visa_sponsorship": "YES",
                "visa_sponsorship_evidence": "We provide work visa sponsorship.",
            },
            title="Backend Engineer",
            body="Relocation is available. We provide work visa sponsorship. Apply now.",
        )
        self.assertTrue(structured["visa_sponsorship_evidence_verified"])
        self.assertTrue(has_verified_sponsorship(structured))

    def test_yes_without_evidence_does_not_qualify(self):
        structured = apply_sponsorship_verification(
            {"visa_sponsorship": "YES", "visa_sponsorship_evidence": None},
            title="Backend Engineer",
            body="International company.",
        )
        self.assertFalse(structured["visa_sponsorship_evidence_verified"])
        self.assertFalse(has_verified_sponsorship(structured))

    def test_yes_with_unmatched_or_paraphrased_evidence_does_not_qualify(self):
        structured = apply_sponsorship_verification(
            {
                "visa_sponsorship": "YES",
                "visa_sponsorship_evidence": "The employer sponsors every applicant.",
            },
            title="Backend Engineer",
            body="Candidates may be eligible to work in Spain.",
        )
        self.assertFalse(has_verified_sponsorship(structured))

    def test_no_unknown_and_invalid_values_never_qualify(self):
        for value in ("NO", "UNKNOWN", "probably", None):
            with self.subTest(value=value):
                structured = apply_sponsorship_verification(
                    {
                        "visa_sponsorship": value,
                        "visa_sponsorship_evidence": "We provide work visa sponsorship.",
                    },
                    title="Backend Engineer",
                    body="We provide work visa sponsorship.",
                )
                self.assertFalse(has_verified_sponsorship(structured))
        self.assertEqual(normalize_sponsorship_value("probably"), "UNKNOWN")

    def test_non_sponsorship_signals_do_not_qualify(self):
        for body in (
            "Relocation support is available.",
            "This is an English-friendly workplace.",
            "Join our international company.",
            "The role is suitable for foreigners.",
            "Visa support may be available in some cases.",
        ):
            with self.subTest(body=body):
                structured = apply_sponsorship_verification(
                    {"visa_sponsorship": "UNKNOWN", "visa_sponsorship_evidence": body},
                    title="Backend Engineer",
                    body=body,
                )
                self.assertFalse(has_verified_sponsorship(structured))

    def test_matching_normalizes_unicode_case_and_whitespace_only(self):
        self.assertTrue(
            evidence_matches_original(
                "WORK VISA   SPONSORSHIP",
                "Senior Engineer",
                "We offer work visa sponsorship to the selected candidate.",
            )
        )
        self.assertFalse(
            evidence_matches_original(
                "We sponsor your visa",
                "Senior Engineer",
                "We offer work visa sponsorship to the selected candidate.",
            )
        )


if __name__ == "__main__":
    unittest.main()
