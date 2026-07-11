from pathlib import Path
import unittest

from radar_engine.models import RawRadarItem
from radar_engine.sources.boe import BOESource


FIXTURE = Path(__file__).parent / "fixtures" / "boe_sample.xml"


class BOESourceTests(unittest.IsolatedAsyncioTestCase):
    def test_fixture_xml_is_parsed_and_normalized(self):
        source = BOESource(max_items=10)
        entries = source.parse_xml(FIXTURE.read_bytes())
        self.assertEqual(len(entries), 4)
        item = source.normalize(entries[0])
        self.assertIsInstance(item, RawRadarItem)
        self.assertEqual(item.source_key, "boe")
        self.assertEqual(item.source_name, "BOE")
        self.assertEqual(item.original_language, "es")
        self.assertEqual(item.external_id, "BOE-A-2026-10001")
        self.assertIn("https://www.boe.es/diario_boe/", item.source_url)
        self.assertIsNotNone(item.published_at)
        self.assertEqual(item.raw_category, "I. Disposiciones generales")

    def test_missing_optional_fields_do_not_crash(self):
        source = BOESource(max_items=10)
        entries = source.parse_xml(FIXTURE.read_bytes())
        item = source.normalize(entries[1])
        self.assertEqual(item.external_id, "BOE-A-2026-10002")
        self.assertEqual(item.original_text, item.original_title)

    async def test_malformed_individual_entry_is_skipped(self):
        source = BOESource(max_items=10)
        entries = source.parse_xml(FIXTURE.read_bytes())

        async def fake_fetch():
            return entries

        source.fetch = fake_fetch
        normalized = await source.fetch_normalized()
        self.assertEqual(len(normalized), 3)

    async def test_fetch_can_be_mocked_without_live_network(self):
        source = BOESource(max_items=10)
        called = False

        async def fake_fetch():
            nonlocal called
            called = True
            return source.parse_xml(FIXTURE.read_bytes())

        source.fetch = fake_fetch
        normalized = await source.fetch_normalized()
        self.assertTrue(called)
        self.assertGreaterEqual(len(normalized), 2)
