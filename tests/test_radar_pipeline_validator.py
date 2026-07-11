from datetime import datetime, timedelta, timezone
import unittest

from tests.test_radar_candidate import make_candidate
from radar_engine.pipeline.validator import validate_candidate


class PipelineValidatorTests(unittest.TestCase):
    def test_valid_candidate_accepted(self):
        result = validate_candidate(make_candidate())
        self.assertTrue(result.is_valid)
        self.assertEqual(result.issues, [])

    def test_multiple_structured_issues_returned(self):
        candidate = make_candidate(title="abcd", body="short")
        candidate.valid_from = datetime(2026, 7, 12, tzinfo=timezone.utc)
        candidate.valid_until = datetime(2026, 7, 11, tzinfo=timezone.utc)
        candidate.trust_level = 9
        result = validate_candidate(candidate)
        self.assertFalse(result.is_valid)
        codes = {(issue.field, issue.code) for issue in result.issues}
        self.assertIn(("title", "too_short"), codes)
        self.assertIn(("body", "too_short"), codes)
        self.assertIn(("valid_until", "before_valid_from"), codes)
        self.assertIn(("trust_level", "out_of_range"), codes)

    def test_blank_fields_rejected(self):
        candidate = make_candidate()
        candidate.title = " "
        candidate.body = " "
        candidate.source_url = " "
        candidate.source_key = " "
        candidate.language = " "
        result = validate_candidate(candidate)
        self.assertFalse(result.is_valid)
        self.assertGreaterEqual(len(result.issues), 5)

    def test_unusable_published_at_rejected(self):
        candidate = make_candidate(published_at=datetime.now(timezone.utc) + timedelta(days=800))
        result = validate_candidate(candidate)
        self.assertFalse(result.is_valid)
        self.assertIn("published_at", [issue.field for issue in result.issues])
