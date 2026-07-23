from __future__ import annotations

from dataclasses import dataclass
import os

from radar_engine.sources.jobs import (
    DomestikaJobsSource,
    EmpleoPublicoSource,
    InfoJobsSource,
    MadridEmpleoSource,
    TecnoempleoSource,
)


FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class SourceStatus:
    key: str
    status: str
    reason: str


@dataclass(frozen=True)
class JobSourceDefinition:
    key: str
    display_name: str
    official_domain: str
    source_type: str
    trust_level: int
    default_enabled: bool
    credential_requirements: tuple[str, ...]
    interval_minutes: int
    attribution: str
    limitations: str


JOB_SOURCE_CATALOG = (
    JobSourceDefinition("infojobs", "InfoJobs", "api.infojobs.net", "official_api", 4, False, ("INFOJOBS_CLIENT_ID", "INFOJOBS_CLIENT_SECRET"), 60, "InfoJobs source URL must be retained", "API credentials and quotas required"),
    JobSourceDefinition("madrid_empleo", "Madrid Empleo", "datos.madrid.es", "official_rss", 5, False, (), 60, "Ayuntamiento de Madrid canonical URL", "Official endpoint may return 403 from some hosting networks"),
    JobSourceDefinition("domestika_jobs", "Domestika Jobs", "domestika.org", "public_atom", 4, False, (), 60, "Domestika canonical job URL", "Feed availability must be smoke-tested before enabling"),
    JobSourceDefinition("tecnoempleo", "Tecnoempleo", "operator_configured", "official_rss", 4, False, ("TECNOEMPLEO_RSS_URL",), 60, "Tecnoempleo canonical job URL", "Only operator-provided RSS/Atom; no HTML fallback"),
    JobSourceDefinition("empleo_publico", "Empleo Público", "administracion.gob.es", "official_public_listing", 5, True, (), 60, "Administracion.gob.es canonical vacancy URL", "Bounded parsing of the official server-rendered public listing"),
)


BLOCKED_SOURCES = (
    SourceStatus("eures", "blocked", "No documented public vacancy retrieval API; partner/public-employment-service access is required."),
    SourceStatus("indeed", "blocked", "Indeed Job Sync is an ATS posting API, not a public vacancy search API."),
    SourceStatus("linkedin_jobs", "blocked", "LinkedIn job APIs require approved partner access and do not provide public job search ingestion."),
    SourceStatus("barcelona_activa", "blocked", "No documented public vacancy feed/API was found; the public search is an authenticated dynamic application."),
    SourceStatus("generalitat_soc", "blocked", "The official Generalitat/SOC listing is dynamic and no documented public vacancy feed/API was verified."),
)

DEFAULT_INFOJOBS_PROVINCES = (
    "Madrid", "Barcelona", "Valencia", "Alicante", "Málaga", "Sevilla", "Baleares",
    "Las Palmas", "Santa Cruz de Tenerife",
)


def enabled(key: str, default: bool = False) -> bool:
    raw = os.getenv(f"RADAR_SOURCE_{key.upper()}_ENABLED")
    if raw is None:
        return default
    return raw.strip().casefold() not in FALSE_VALUES


def source_interval_minutes(key: str, default: int = 60) -> int:
    try:
        return max(5, int(os.getenv(f"RADAR_SOURCE_{key.upper()}_INTERVAL_MINUTES", str(default))))
    except ValueError:
        return default


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def configured_job_sources():
    common = {
        "timeout_seconds": _bounded_int("RADAR_JOB_SOURCE_TIMEOUT_SECONDS", 12, 1, 60),
        "retries": _bounded_int("RADAR_JOB_SOURCE_RETRIES", 2, 0, 4),
        "max_items": _bounded_int("RADAR_JOB_SOURCE_MAX_ITEMS", 50, 1, 200),
    }
    sources = []
    if enabled("infojobs") and os.getenv("INFOJOBS_CLIENT_ID") and os.getenv("INFOJOBS_CLIENT_SECRET"):
        provinces = tuple(
            value.strip() for value in os.getenv("RADAR_INFOJOBS_PROVINCES", ",".join(DEFAULT_INFOJOBS_PROVINCES)).split(",")
            if value.strip()
        )
        sources.append(
            InfoJobsSource(
                client_id=os.environ["INFOJOBS_CLIENT_ID"],
                client_secret=os.environ["INFOJOBS_CLIENT_SECRET"],
                keywords=os.getenv("RADAR_INFOJOBS_KEYWORDS", ""),
                provinces=provinces,
                page_size=_bounded_int("RADAR_INFOJOBS_PAGE_SIZE", 20, 10, 50),
                max_pages=_bounded_int("RADAR_INFOJOBS_MAX_PAGES_PER_CYCLE", 2, 1, 10),
                **common,
            )
        )
    if enabled("madrid_empleo"):
        sources.append(MadridEmpleoSource(**common))
    if enabled("domestika_jobs"):
        sources.append(DomestikaJobsSource(**common))
    if enabled("empleo_publico", default=True):
        sources.append(
            EmpleoPublicoSource(
                max_pages=_bounded_int("RADAR_EMPLEO_PUBLICO_MAX_PAGES_PER_CYCLE", 2, 1, 10),
                **common,
            )
        )
    feed_url = os.getenv("TECNOEMPLEO_RSS_URL", "").strip()
    if enabled("tecnoempleo") and feed_url:
        sources.append(TecnoempleoSource(feed_url=feed_url, **common))
    return sources
