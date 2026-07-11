from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

from radar_engine.models import RawRadarItem
from radar_engine.source_manager import SourceManager
from radar_engine.sources.boe import BOESource, BOERawEntry


FIXTURE = Path(__file__).parent / "fixtures" / "boe_sample.xml"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

    def test_valid_relative_document_url_is_resolved(self):
        source = BOESource(max_items=10)
        entries = source.parse_xml(FIXTURE.read_bytes())
        item = source.normalize(entries[0])
        self.assertEqual(item.source_url, "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-10001")

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

    async def test_total_network_failure_becomes_fatal_report(self):
        source = BOESource(days_back=2)

        def fail_read(url):
            raise OSError("network unavailable")

        source._read_url = fail_read
        with self.assertRaisesRegex(RuntimeError, "failed for all attempted"):
            await source.fetch()

        manager = SourceManager(store_func=lambda item: None)
        manager.register(source)
        report = await manager.ingest_source("boe")
        self.assertEqual(report.fetched_count, 0)
        self.assertGreaterEqual(report.failed_count, 1)
        self.assertIn("fetch failed", report.errors[0])

    async def test_partial_network_failure_returns_successful_entries(self):
        source = BOESource(days_back=2, max_items=10)
        calls = []

        def read_url(url):
            calls.append(url)
            if len(calls) == 1:
                raise OSError("temporary unavailable")
            return FIXTURE.read_bytes()

        source._read_url = read_url
        entries = await source.fetch()
        self.assertEqual(len(calls), 2)
        self.assertGreaterEqual(len(entries), 2)

    def test_missing_identity_does_not_use_boe_homepage(self):
        element = ET.fromstring("<item><titulo>Sin identidad</titulo><texto>Texto</texto></item>")
        source = BOESource()
        with self.assertRaisesRegex(ValueError, "missing both external identifier and document URL"):
            source.normalize(BOERawEntry(element, None, None))


class RadarRunnerTests(unittest.TestCase):
    def test_documented_script_help_runs_without_database(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_source.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run a manual Radar source ingestion", result.stdout)
