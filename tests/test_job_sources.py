import json
import os
import unittest
from unittest.mock import patch

from database.db import INITIAL_RADAR_SOURCES, configured_radar_source_states
from radar_engine.source_config import BLOCKED_SOURCES, JOB_SOURCE_CATALOG, configured_job_sources
from radar_engine.sources.jobs import (
    DomestikaJobsSource, EmpleoPublicoSource, InfoJobsSource, MadridEmpleoSource,
    TecnoempleoSource, job_fingerprint,
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

EMPLEO_PUBLICO_HTML = """<html><body>
<article>
  <a href="/pagFront/ofertasempleopublico/detalleEmpleo.htm?idConvocatoria=221903&amp;retorno=x">
    TÉCNICO/A SUPERIOR - Medio Ambiental
  </a>
  <div>Ref: 221903</div><div>Plazas: 1</div><div>Fin de plazo: 02/08/2026</div>
  <div>Titulación: Grado en Ciencias Ambientales</div>
  <div>Ubicación: AUTONÓMICO - BALEARS, ILLES</div>
  <div>Órgano convocante: Fundación Balear de Innovación y Tecnología</div>
</article>
</body></html>""".encode()


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
        source = InfoJobsSource(client_id="id", client_secret="secret", provinces=(), max_pages=1, retries=0)
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

    def test_empleo_publico_maps_official_listing_to_canonical_job(self):
        source = EmpleoPublicoSource(max_pages=1, retries=0)
        with patch.object(source, "_read", return_value=EMPLEO_PUBLICO_HTML):
            rows = source._fetch_sync()
        item = source.normalize(rows[0])
        self.assertEqual(item.external_id, "221903")
        self.assertEqual(item.original_title, "TÉCNICO/A SUPERIOR - Medio Ambiental")
        self.assertEqual(item.valid_until.date().isoformat(), "2026-08-02")
        self.assertEqual(item.metadata["employer"], "Fundación Balear de Innovación y Tecnología")
        self.assertEqual(item.metadata["content_type"], "job")
        self.assertIn("idConvocatoria=221903", item.source_url)

    def test_empleo_publico_empty_malformed_and_duplicate_results_are_safe(self):
        source = EmpleoPublicoSource(max_pages=1, retries=0)
        with patch.object(source, "_read", return_value=b"<html><body>Sin resultados</body></html>"):
            self.assertEqual(source._fetch_sync(), [])
        duplicate = EMPLEO_PUBLICO_HTML.replace(b"</body>", EMPLEO_PUBLICO_HTML.split(b"<article>")[1].split(b"</article>")[0] + b"</body>")
        with patch.object(source, "_read", return_value=duplicate):
            self.assertEqual(len(source._fetch_sync()), 1)
        with self.assertRaisesRegex(ValueError, "missing reference"):
            source.normalize_job({"title": "Incomplete"})

    def test_empleo_publico_pagination_is_bounded(self):
        source = EmpleoPublicoSource(max_pages=2, max_items=100, retries=0)
        calls = []

        def read(url):
            calls.append(url)
            return EMPLEO_PUBLICO_HTML

        with patch.object(source, "_read", side_effect=read):
            source._fetch_sync()
        self.assertEqual(len(calls), 1)
        self.assertIn("tam=50", calls[0])
        self.assertIn("desde=1", calls[0])

    def test_infojobs_uses_authentication_and_bounded_pagination(self):
        source = InfoJobsSource(
            client_id="client", client_secret="secret", provinces=("Madrid",),
            keywords="python", page_size=20, max_pages=2, max_items=50, retries=0,
        )
        calls = []

        def read(url, headers=None):
            calls.append((url, headers))
            page = 1 if "page=1" in url else 2
            return json.dumps({"offers": [{"id": str(page)}], "totalPages": 2}).encode()

        with patch.object(source, "_read", side_effect=read):
            rows = source._fetch_sync()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(call[1]["Authorization"].startswith("Basic ") for call in calls))
        self.assertTrue(all("secret" not in call[0] for call in calls))
        self.assertIn("province=Madrid", calls[0][0])
        self.assertIn("q=python", calls[0][0])

    def test_infojobs_disabled_without_both_credentials(self):
        env = {"RADAR_SOURCE_INFOJOBS_ENABLED": "true", "INFOJOBS_CLIENT_ID": "id"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual([source.source_key for source in configured_job_sources()], ["empleo_publico"])

    def test_madrid_closed_call_is_preserved_as_expired_for_audit(self):
        source = MadridEmpleoSource(retries=0)
        row = {
            "guid": "closed", "title": "Auxiliar Administrativo", "link": "https://madrid.es/closed",
            "description": "Convocatoria oficial de Auxiliar Administrativo cuyo plazo cerrado consta oficialmente.",
        }
        item = source.normalize(row)
        self.assertTrue(item.metadata["is_expired"])
        self.assertEqual(item.metadata["source_status"], "convocatoria cerrada")

    def test_madrid_static_workforce_dataset_is_rejected(self):
        source = MadridEmpleoSource(retries=0)
        row = {
            "guid": "static", "title": "Relación de puestos de trabajo", "link": "https://madrid.es/static",
            "description": "Relación de puestos de trabajo y plantilla de personal del Ayuntamiento de Madrid.",
        }
        with self.assertRaisesRegex(ValueError, "static workforce"):
            source.normalize(row)

    def test_feed_html_is_rejected_and_tecnoempleo_url_is_validated(self):
        source = DomestikaJobsSource(retries=0)
        with patch.object(source, "_read", return_value=b"<html><body>login</body></html>"):
            with self.assertRaisesRegex(ValueError, "HTML"):
                source._fetch_sync()
        with self.assertRaisesRegex(ValueError, "http or https"):
            TecnoempleoSource(feed_url="ftp://example.es/jobs.xml")

    def test_explicit_deadline_is_extracted_but_publication_date_is_not_reused(self):
        source = MadridEmpleoSource(retries=0)
        explicit = {
            "guid": "deadline", "title": "Arquitecto Municipal", "link": "https://madrid.es/deadline",
            "description": "Convocatoria oficial. Plazo de presentación de solicitudes: 31/12/2026.",
            "pubDate": "Thu, 16 Jul 2026 10:00:00 +0200",
        }
        no_deadline = {**explicit, "guid": "none", "description": "Convocatoria oficial publicada el 16/07/2026 sin plazo indicado."}
        self.assertEqual(source.normalize_job(explicit).deadline.date().isoformat(), "2026-12-31")
        self.assertIsNone(source.normalize_job(no_deadline).deadline)

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
        self.assertEqual(
            {item.key for item in BLOCKED_SOURCES},
            {"eures", "indeed", "linkedin_jobs", "barcelona_activa", "generalitat_soc"},
        )
        self.assertTrue(all(item.status in {"blocked", "not_integrated"} and item.reason for item in BLOCKED_SOURCES))

    def test_requested_source_catalog_has_accurate_trust_type_and_status(self):
        catalog = {item.key: item for item in JOB_SOURCE_CATALOG}
        empleo = catalog["empleo_publico"]
        self.assertEqual((empleo.source_type, empleo.trust_level, empleo.default_enabled), ("official_public_listing", 5, True))
        blocked = {item.key: item.status for item in BLOCKED_SOURCES}
        self.assertEqual(blocked["eures"], "blocked")
        self.assertEqual(blocked["barcelona_activa"], "blocked")
        self.assertEqual(blocked["generalitat_soc"], "blocked")

    def test_registry_lists_requested_jobs_and_keeps_other_government_sources_active(self):
        rows = {row[0]: row for row in INITIAL_RADAR_SOURCES}
        for name in ("EURES", "Barcelona Activa", "Generalitat/SOC", "Empleo Público"):
            self.assertEqual((rows[name][1], rows[name][3], rows[name][4]), ("Jobs", "official", 5))
        with patch.dict(os.environ, {}, clear=True):
            states = configured_radar_source_states()
        self.assertFalse(states["BOE"])
        self.assertFalse(states["EURES"])
        self.assertFalse(states["Barcelona Activa"])
        self.assertFalse(states["Generalitat/SOC"])
        self.assertTrue(states["Empleo Público"])
        for name in ("SEPE", "Seguridad Social", "Agencia Tributaria", "Ministerio de Inclusión"):
            self.assertIn(name, rows)

    def test_sources_are_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual([source.source_key for source in configured_job_sources()], ["empleo_publico"])

    def test_enabled_sources_are_independent(self):
        env = {"RADAR_SOURCE_MADRID_EMPLEO_ENABLED": "1", "RADAR_SOURCE_DOMESTIKA_JOBS_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                [s.source_key for s in configured_job_sources()],
                ["madrid_empleo", "domestika_jobs", "empleo_publico"],
            )

    def test_invalid_shared_limits_fall_back_safely(self):
        env = {"RADAR_SOURCE_MADRID_EMPLEO_ENABLED": "1", "RADAR_JOB_SOURCE_TIMEOUT_SECONDS": "bad", "RADAR_JOB_SOURCE_RETRIES": "99"}
        with patch.dict(os.environ, env, clear=True):
            source = configured_job_sources()[0]
        self.assertEqual(source.timeout_seconds, 12)
        self.assertEqual(source.retries, 4)
