from pathlib import Path
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from unittest.mock import patch

from radar_engine.models import RawRadarItem
from radar_engine.source_manager import SourceManager, build_default_source_manager
from radar_engine.sources.boe import (
    BOE_LOOKBACK_ENV,
    BOENoEditionError,
    BOERequestError,
    BOESource,
    BOERawEntry,
    BOEXMLValidationError,
)


FIXTURE = Path(__file__).parent / "fixtures" / "boe_sample.xml"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeBOEResponse:
    def __init__(self, payload: bytes, content_type: str = "text/xml; charset=utf-8"):
        self.payload = payload
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


class BOESourceTests(unittest.IsolatedAsyncioTestCase):
    def test_daily_xml_url_uses_official_boe_date_path(self):
        source = BOESource(max_items=10)
        url = source._daily_xml_url(source._parse_date("2024-07-13").date())
        self.assertEqual(url, "https://www.boe.es/boe/dias/2024/07/13/sumario.xml")

    def test_lookback_defaults_to_env_and_is_clamped(self):
        with patch.dict("os.environ", {BOE_LOOKBACK_ENV: "45"}):
            self.assertEqual(BOESource().days_back, 30)
        with patch.dict("os.environ", {BOE_LOOKBACK_ENV: "0"}):
            self.assertEqual(BOESource().days_back, 1)
        with patch.dict("os.environ", {BOE_LOOKBACK_ENV: "bad"}):
            self.assertEqual(BOESource().days_back, 7)

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

    async def test_no_edition_dates_return_empty_nonfatal_result(self):
        source = BOESource(days_back=2)

        def no_edition(url):
            raise BOENoEditionError("HTTP 404")

        source._read_url = no_edition
        entries = await source.fetch()
        self.assertEqual(entries, [])

        manager = SourceManager(store_func=lambda item: None)
        manager.register(source)
        report = await manager.ingest_source("boe")
        self.assertEqual(report.fetched_count, 0)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.errors, [])

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

    async def test_fetch_stops_after_first_valid_recent_edition(self):
        source = BOESource(days_back=5, max_items=10)
        calls = []

        def read_url(url):
            calls.append(url)
            return FIXTURE.read_bytes()

        source._read_url = read_url
        entries = await source.fetch()
        self.assertEqual(len(calls), 1)
        self.assertGreaterEqual(len(entries), 2)

    def test_html_success_response_is_rejected(self):
        source = BOESource()
        with self.assertRaisesRegex(BOEXMLValidationError, "HTML"):
            source._validate_xml_payload(b"<html><title>Error</title></html>", "text/html; charset=utf-8")

    def test_malformed_xml_is_rejected(self):
        source = BOESource()
        with self.assertRaisesRegex(BOEXMLValidationError, "malformed"):
            source.parse_xml(b"<?xml version='1.0'?><sumario><diario>")

    def test_unexpected_xml_shape_is_rejected(self):
        source = BOESource()
        with self.assertRaisesRegex(BOEXMLValidationError, "unexpected BOE XML root"):
            source.parse_xml(b"<?xml version='1.0'?><not_boe></not_boe>")

    def test_http_400_and_404_are_treated_as_no_edition(self):
        source = BOESource()
        for status in (400, 404):
            with self.subTest(status=status):
                error = HTTPError("https://www.boe.es/test", status, "missing", {}, None)
                with patch("radar_engine.sources.boe.urlopen", side_effect=error):
                    with self.assertRaises(BOENoEditionError):
                        source._read_url("https://www.boe.es/test")

    def test_http_429_and_500_are_request_failures(self):
        source = BOESource()
        for status in (429, 500):
            with self.subTest(status=status):
                error = HTTPError("https://www.boe.es/test", status, "upstream", {}, None)
                with patch("radar_engine.sources.boe.urlopen", side_effect=error):
                    with self.assertRaises(BOERequestError):
                        source._read_url("https://www.boe.es/test")

    def test_read_url_sends_application_user_agent_and_accept_header(self):
        source = BOESource()
        seen = {}

        def fake_urlopen(request, timeout):
            seen["timeout"] = timeout
            seen["user_agent"] = request.get_header("User-agent")
            seen["accept"] = request.get_header("Accept")
            return FakeBOEResponse(FIXTURE.read_bytes())

        with patch("radar_engine.sources.boe.urlopen", side_effect=fake_urlopen):
            payload = source._read_url("https://www.boe.es/boe/dias/2026/07/11/sumario.xml")

        self.assertTrue(payload.startswith(b"<?xml"))
        self.assertEqual(seen["user_agent"], "VitrinSpainRadar/1.0")
        self.assertEqual(seen["accept"], "application/xml,text/xml")
        self.assertEqual(seen["timeout"], source.timeout_seconds)

    def test_default_source_manager_passes_boe_lookback_override(self):
        manager = build_default_source_manager(boe_days_back=9)
        source = manager.get_source("boe")
        self.assertEqual(source.days_back, 9)

    def test_missing_identity_does_not_use_boe_homepage(self):
        element = ET.fromstring("<item><titulo>Sin identidad</titulo><texto>Texto</texto></item>")
        source = BOESource()
        with self.assertRaisesRegex(ValueError, "missing both external identifier and document URL"):
            source.normalize(BOERawEntry(element, None, None))

    def test_deceptive_boe_hostname_is_rejected(self):
        source = BOESource()
        self.assertIsNone(source._document_url("https://fakeboe.es/diario_boe/txt.php?id=BOE-A-1", None))
        self.assertEqual(
            source._document_url("https://www.boe.es/diario_boe/txt.php?id=BOE-A-1", None),
            "https://www.boe.es/diario_boe/txt.php?id=BOE-A-1",
        )


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
        self.assertIn("--lookback-days", result.stdout)
