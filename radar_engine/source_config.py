from __future__ import annotations

from dataclasses import dataclass
import os

from radar_engine.sources.jobs import DomestikaJobsSource, InfoJobsSource, MadridEmpleoSource, TecnoempleoSource


FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class SourceStatus:
    key: str
    status: str
    reason: str


BLOCKED_SOURCES = (
    SourceStatus("eures", "blocked", "No documented public vacancy retrieval API; partner/public-employment-service access is required."),
    SourceStatus("indeed", "blocked", "Indeed Job Sync is an ATS posting API, not a public vacancy search API."),
    SourceStatus("linkedin_jobs", "blocked", "LinkedIn job APIs require approved partner access and do not provide public job search ingestion."),
    SourceStatus("barcelona_activa", "blocked", "No documented public vacancy feed/API was found; the public search is an authenticated dynamic application."),
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
        sources.append(InfoJobsSource(client_id=os.environ["INFOJOBS_CLIENT_ID"], client_secret=os.environ["INFOJOBS_CLIENT_SECRET"], **common))
    if enabled("madrid_empleo"):
        sources.append(MadridEmpleoSource(**common))
    if enabled("domestika_jobs"):
        sources.append(DomestikaJobsSource(**common))
    feed_url = os.getenv("TECNOEMPLEO_RSS_URL", "").strip()
    if enabled("tecnoempleo") and feed_url:
        sources.append(TecnoempleoSource(feed_url=feed_url, **common))
    return sources
