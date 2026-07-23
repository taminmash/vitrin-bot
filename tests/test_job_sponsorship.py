import unittest

from radar_engine.job_sponsorship import (
    apply_sponsorship_verification,
    evidence_matches_original,
    has_explicit_support_statement,
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

    def test_title_body_boundary_cannot_create_synthetic_match(self):
        self.assertFalse(
            evidence_matches_original(
                "We provide complete work visa sponsorship support.",
                "We provide complete work",
                "visa sponsorship support.",
            )
        )

    def test_trivial_and_generic_evidence_is_rejected(self):
        for evidence in ("visa", "sponsorship", "work permit"):
            with self.subTest(evidence=evidence):
                self.assertFalse(has_explicit_support_statement(evidence))
                self.assertFalse(evidence_matches_original(evidence, evidence, evidence))

    def test_explicit_english_sponsorship_sentence_is_accepted(self):
        evidence = "We provide work visa sponsorship for successful candidates."
        self.assertTrue(evidence_matches_original(evidence, "Engineer", f"Benefits: {evidence} Apply now."))

    def test_explicit_spanish_work_permit_support_sentence_is_accepted(self):
        evidence = "La empresa ofrece apoyo para tramitar el permiso de trabajo."
        self.assertTrue(evidence_matches_original(evidence, "Ingeniero", f"Beneficios: {evidence}"))

    def test_explicit_english_denials_never_verify_even_when_ai_says_yes(self):
        denials = (
            "We do not offer visa sponsorship for this role.",
            "Visa sponsorship is not available for this position.",
            "No work permit support is provided by the employer.",
            "Sponsorship will not be provided for this role.",
            "We are unable to sponsor a work visa for candidates.",
        )
        for evidence in denials:
            with self.subTest(evidence=evidence):
                self.assertFalse(has_explicit_support_statement(evidence))
                self.assertFalse(evidence_matches_original(evidence, "Engineer", evidence))
                structured = apply_sponsorship_verification(
                    {"visa_sponsorship": "YES", "visa_sponsorship_evidence": evidence},
                    title="Engineer",
                    body=evidence,
                )
                self.assertFalse(structured["visa_sponsorship_evidence_verified"])
                self.assertFalse(has_verified_sponsorship(structured))

    def test_explicit_spanish_denials_never_verify_even_when_ai_says_yes(self):
        denials = (
            "No ofrecemos patrocinio de visado para este puesto.",
            "No se ofrece apoyo para el permiso de trabajo.",
            "El patrocinio de visa no está disponible para este puesto.",
        )
        for evidence in denials:
            with self.subTest(evidence=evidence):
                self.assertFalse(has_explicit_support_statement(evidence))
                structured = apply_sponsorship_verification(
                    {"visa_sponsorship": "YES", "visa_sponsorship_evidence": evidence},
                    title="Ingeniero",
                    body=evidence,
                )
                self.assertFalse(structured["visa_sponsorship_evidence_verified"])
                self.assertFalse(has_verified_sponsorship(structured))

    def test_unrelated_negation_does_not_override_explicit_positive_support(self):
        evidence = "The role is not remote, but we offer work visa sponsorship to successful candidates."
        self.assertTrue(has_explicit_support_statement(evidence))
        self.assertTrue(evidence_matches_original(evidence, "Engineer", evidence))

    def test_matching_normalizes_unicode_case_and_whitespace(self):
        self.assertTrue(
            evidence_matches_original(
                "WE OFFER WORK VISA   SPONSORSHIP TO THE SELECTED CANDIDATE.",
                "Senior Engineer",
                "We offer work visa\u00a0sponsorship to the selected candidate.",
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
