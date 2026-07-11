import unittest

from radar_engine.pipeline.candidate import SourceInfo, StoredRawRadarItem
from radar_engine.pipeline.normalizer import normalize_raw_item


class PipelineNormalizerTests(unittest.TestCase):
    def test_maps_raw_row_without_semantic_rewriting(self):
        raw = StoredRawRadarItem(
            id="raw-1",
            source_key="boe",
            external_id="BOE-A-1",
            source_name="BOE",
            source_url="https://www.boe.es/a",
            canonical_url="https://www.boe.es/a",
            original_title="  Titulo oficial  ",
            original_text="Linea 1\r\n\r\n\r\nLinea 2\x00",
            original_language="es",
            published_at=None,
            valid_from=None,
            valid_until=None,
            raw_category="I",
            raw_location="Spain",
            metadata={"boe_id": "BOE-A-1"},
        )
        source = SourceInfo("boe", "BOE", "Government", "official", 5, "Spain")
        candidate = normalize_raw_item(raw, source)
        self.assertEqual(candidate.title, "Titulo oficial")
        self.assertEqual(candidate.body, "Linea 1\n\nLinea 2")
        self.assertEqual(candidate.language, "es")
        self.assertEqual(candidate.source_url, raw.source_url)
        self.assertEqual(candidate.source_category, "I")
        self.assertEqual(candidate.source_location, "Spain")
        self.assertEqual(candidate.source_type, "official")
        self.assertNotIn("ai_summary", candidate.__dict__)
        self.assertNotIn("audience", candidate.__dict__)
