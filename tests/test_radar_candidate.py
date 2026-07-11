from datetime import datetime, timezone
import unittest

from radar_engine.pipeline.candidate import RadarCandidate


def make_candidate(**overrides):
    data = {
        "raw_item_id": "00000000-0000-0000-0000-000000000001",
        "source_key": " boe ",
        "source_name": " BOE ",
        "external_id": " BOE-A-1 ",
        "title": " Candidate title ",
        "body": " Candidate body text ",
        "language": " es ",
        "source_url": " https://www.boe.es/test ",
        "canonical_url": None,
        "published_at": datetime(2026, 7, 11, tzinfo=timezone.utc),
        "valid_from": None,
        "valid_until": None,
        "source_category": " Law ",
        "source_location": None,
        "source_type": " Official ",
        "trust_level": 5,
    }
    data.update(overrides)
    return RadarCandidate(**data)


class RadarCandidateTests(unittest.TestCase):
    def test_valid_candidate_trims_and_defaults(self):
        candidate = make_candidate()
        self.assertEqual(candidate.source_key, "boe")
        self.assertEqual(candidate.country, "Spain")
        self.assertEqual(candidate.candidate_status, "pending_ai")
        self.assertEqual(candidate.metadata, {})
        self.assertEqual(candidate.trust_level, 5)

    def test_blank_required_field_rejected(self):
        with self.assertRaises(ValueError):
            make_candidate(title=" ")

    def test_invalid_trust_level_rejected(self):
        with self.assertRaises(ValueError):
            make_candidate(trust_level=6)
