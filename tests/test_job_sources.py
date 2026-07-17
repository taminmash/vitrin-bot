import json
import os
import unittest
from unittest.mock import patch

from radar_engine.source_config import BLOCKED_SOURCES, configured_job_sources
from radar_engine.sources.jobs import (
    DomestikaJobsSource, InfoJobsSource, MadridEmpleoSource, TecnoempleoSource, job_fingerprint,
)


RSS = b"""<?xml version='1.0'?><rss><channel><item>
<guid>job-1</guid><title>Python Developer</title>
<description>Desarrollo de servicios Python para una empresa tecnologica estable.</description>
<link>https://example.es/jobs/1?utm_source=rss</link><pubDate>Thu, 16 Jul 2026 10:00:00 +0200</pubDate>
</item></channel></rss>"""

ATOM = b"""<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry>
<id>job-2</id><title>Product Designer</title><summary>Diseno de productos digitales para clientes de toda Espana.</summary>
<link href='https://example.es/jobs/2'/><updated>2026-07-16T10:00:00Z</updated>
</entry></feed>"""


class JobSourceTests(unittest.TestCase):
    def test_madrid_rss_fetch_normalize_and_spain_target(self):
        source = MadridEmpleoSource(retries=0)
        with patch.object(source, "_read", return_value=RSS):
            rows = source._fetch_sync()
        item = source.normalize(rows[0])
        self.assertEqual(item.raw_location, "Madrid, Comunidad de Madrid")
        self.assertEqual(item.metadata["content_type"], "job")
        self.assertTrue(item.metadata["job_fingerprint"])

    def test_domestika_atom_is_supported(self):
        source = DomestikaJobsSource(retries=0)
        with patch.object(source, "_read", return_value=ATOM):
            rows = source._fetch_sync()
        self.assertEqual(source.normalize(rows[0]).original_title, "Product Designer")

    def test_tecnoempleo_requires_official_feed_configuration(self):
        with self.assertRaises(ValueError):
            TecnoempleoSource(feed_url="")

    def test_infojobs_api_maps_structured_fields(self):
        source = InfoJobsSource(client_id="id", client_secret="secret", retries=0)
        payload = {"offers": [{
            "id": "ij-1", "title": "Data Engineer", "link": "https://infojobs.net/offer/ij-1",
            "description": "Construccion y mantenimiento de plataformas de datos empresariales.",
            "author": {"name": "Acme"}, "city": "Barcelona", "province": {"value": "Barcelona"},
            "salaryDescription": "40k-50k", "contractType": {"value": "Indefinido"},
        }]}
        with patch.object(source, "_read", return_value=json.dumps(payload).encode()):
            raw = source._fetch_sync()[0]
        item = source.normalize(raw)
        self.assertEqual(item.metadata["employer"], "Acme")
        self.assertEqual(item.metadata["salary"], "40k-50k")
        self.assertEqual(item.metadata["contract_type"], "Indefinido")

    def test_fingerprint_matches_across_sources(self):
        self.assertEqual(
            job_fingerprint("Python Developer", "ACME, S.L.", "Madrid"),
            job_fingerprint("python developer", "acme s l", "madrid"),
        )

    def test_stale_and_low_information_jobs_are_filtered(self):
        source = MadridEmpleoSource(retries=0)
        row = {"guid": "x", "title": "Job", "description": "short", "link": "https://example.es/x"}
        with self.assertRaisesRegex(ValueError, "too short"):
            source.normalize(row)

    def test_blocked_sources_have_explicit_reasons_and_no_adapters(self):
        self.assertEqual({item.key for item in BLOCKED_SOURCES}, {"eures", "indeed", "linkedin_jobs", "barcelona_activa"})
        self.assertTrue(all(item.status == "blocked" and item.reason for item in BLOCKED_SOURCES))

    def test_sources_are_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(configured_job_sources(), [])

    def test_enabled_sources_are_independent(self):
        env = {"RADAR_SOURCE_MADRID_EMPLEO_ENABLED": "1", "RADAR_SOURCE_DOMESTIKA_JOBS_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual([s.source_key for s in configured_job_sources()], ["madrid_empleo", "domestika_jobs"])

    def test_invalid_shared_limits_fall_back_safely(self):
        env = {"RADAR_SOURCE_MADRID_EMPLEO_ENABLED": "1", "RADAR_JOB_SOURCE_TIMEOUT_SECONDS": "bad", "RADAR_JOB_SOURCE_RETRIES": "99"}
        with patch.dict(os.environ, env, clear=True):
            source = configured_job_sources()[0]
        self.assertEqual(source.timeout_seconds, 12)
        self.assertEqual(source.retries, 4)
