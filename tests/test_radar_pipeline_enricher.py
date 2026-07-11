import unittest

from tests.test_radar_candidate import make_candidate
from radar_engine.pipeline.enricher import PIPELINE_VERSION, enrich_candidate


class PipelineEnricherTests(unittest.TestCase):
    def test_adds_only_deterministic_source_metadata(self):
        candidate = make_candidate(metadata={"source_registry_category": "Government"}, country="")
        enriched = enrich_candidate(candidate)
        self.assertEqual(enriched.country, "Spain")
        self.assertTrue(enriched.metadata["official_source"])
        self.assertTrue(enriched.metadata["government_source"])
        self.assertEqual(enriched.metadata["pipeline_version"], PIPELINE_VERSION)
        forbidden = {"category", "audience", "city", "urgency", "summary", "priority"}
        self.assertTrue(forbidden.isdisjoint(enriched.metadata.keys()))

    def test_idempotent(self):
        candidate = make_candidate(metadata={"source_registry_category": "Government"})
        first = enrich_candidate(candidate)
        second = enrich_candidate(first)
        self.assertEqual(first, second)
