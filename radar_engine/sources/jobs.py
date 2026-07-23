from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import time
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from radar_engine.models import RawRadarItem
from radar_engine.job_expiration import job_temporal_state, parse_source_datetime
from radar_engine.sources.base import BaseRadarSource


USER_AGENT = "VitrinSpainRadar/1.0 (+https://t.me/vitrinspain)"


def _explicit_deadline(text: str | None) -> datetime | None:
    value = text or ""
    patterns = (
        r"(?:plazo|fecha\s+l[ií]mite|presentaci[oó]n\s+de\s+solicitudes)[^\d]{0,50}(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(?:hasta\s+el)[^\d]{0,20}(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return parse_source_datetime(match.group(1), end_of_day=True)
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value)))).strip()
    return cleaned or None


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def job_fingerprint(title: str, employer: str | None, location: str | None) -> str:
    def canonical(value: str | None) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
    value = "|".join((canonical(title), canonical(employer), canonical(location)))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NormalizedJob:
    external_id: str
    title: str
    description: str
    url: str
    employer: str | None = None
    city: str | None = None
    region: str | None = None
    salary: str | None = None
    contract_type: str | None = None
    working_hours: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    deadline: datetime | None = None
    remote: bool | None = None
    experience: str | None = None
    education: str | None = None
    category: str | None = None
    subcategory: str | None = None
    source_status: str | None = None
    reference_number: str | None = None
    application_url: str | None = None
    raw: dict[str, Any] | None = None


class JobSourceAdapter(BaseRadarSource):
    country = "Spain"

    def __init__(self, *, timeout_seconds: int = 12, retries: int = 2, max_items: int = 50):
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.retries = min(4, max(0, int(retries)))
        self.max_items = min(200, max(1, int(max_items)))

    async def fetch(self) -> list[Any]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[Any]:
        raise NotImplementedError

    def _read(self, url: str, *, headers: dict[str, str] | None = None) -> bytes:
        request_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/atom+xml, application/rss+xml, application/xml, text/html",
        }
        request_headers.update(headers or {})
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(Request(url, headers=request_headers), timeout=self.timeout_seconds) as response:
                    return response.read()
            except Exception as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"{self.source_key} request failed after {self.retries + 1} attempt(s): {last_error}")

    def normalize(self, raw_item: Any) -> RawRadarItem:
        job = self.normalize_job(raw_item)
        if len(job.description) < 40:
            raise ValueError("job description is too short")
        location = ", ".join(value for value in (job.city, job.region) if value) or "Spain"
        metadata = {
            "content_type": "job",
            "employer": job.employer,
            "city": job.city,
            "region": job.region,
            "salary": job.salary,
            "contract_type": job.contract_type,
            "working_hours": job.working_hours,
            "remote": job.remote,
            "source_published_at": job.published_at.isoformat() if job.published_at else None,
            "source_updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "application_deadline": job.deadline.isoformat() if job.deadline else None,
            "deadline_unknown": job.deadline is None,
            "experience_required": job.experience,
            "education": job.education,
            "category": job.category,
            "subcategory": job.subcategory,
            "source_status": job.source_status,
            "reference_number": job.reference_number,
            "application_url": job.application_url,
            "job_fingerprint": job_fingerprint(job.title, job.employer, location),
            "provenance": [{"source_key": self.source_key, "external_id": job.external_id, "url": job.url}],
        }
        temporal = job_temporal_state({"published_at": job.published_at, "valid_until": job.deadline, "metadata": metadata})
        metadata.update({
            "is_expired": temporal.expired,
            "expiration_reason": temporal.expiration_reason,
            "stale_review": temporal.stale,
        })
        return RawRadarItem(
            source_key=self.source_key, external_id=job.external_id, source_name=self.source_name,
            source_url=job.url, canonical_url=job.url, original_title=job.title,
            original_text=job.description, original_language="es", published_at=job.published_at,
            valid_from=job.published_at, valid_until=job.deadline, raw_category="jobs",
            raw_location=location, metadata={key: value for key, value in metadata.items() if value is not None},
        )

    def normalize_job(self, raw_item: Any) -> NormalizedJob:
        raise NotImplementedError


class FeedJobSource(JobSourceAdapter):
    feed_url: str

    def _fetch_sync(self) -> list[dict[str, str]]:
        payload = self._read(self.feed_url)
        if payload.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise ValueError(f"{self.source_key} endpoint returned HTML instead of RSS/Atom")
        root = ET.fromstring(payload)
        root_name = root.tag.rsplit("}", 1)[-1].casefold()
        if root_name not in {"rss", "feed", "rdf"}:
            raise ValueError(f"{self.source_key} endpoint is not RSS or Atom")
        entries = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
        if not entries:
            raise ValueError(f"{self.source_key} feed contains no job entries")
        return [self._feed_entry(entry) for entry in entries[: self.max_items]]

    def _feed_entry(self, entry: ET.Element) -> dict[str, str]:
        result: dict[str, str] = {}
        for child in entry.iter():
            name = child.tag.rsplit("}", 1)[-1]
            if name == "link" and child.attrib.get("href"):
                result["link"] = child.attrib["href"]
            elif child.text and name not in result:
                result[name] = child.text
        return result

    def normalize_job(self, item: Any) -> NormalizedJob:
        if not isinstance(item, dict):
            raise ValueError("feed item must be a dictionary")
        title = _text(item.get("title"))
        url = _text(item.get("link") or item.get("guid") or item.get("id"))
        description = _text(item.get("description") or item.get("summary") or item.get("content") or title)
        if not title or not url or not description:
            raise ValueError("feed job is missing title, URL, or description")
        external_id = _text(item.get("guid") or item.get("id")) or url
        return NormalizedJob(
            external_id=external_id, title=title, description=description, url=url,
            employer=_text(item.get("author") or item.get("company")),
            city=_text(item.get("city")), region=_text(item.get("region")),
            published_at=_datetime(item.get("pubDate") or item.get("published") or item.get("updated")),
            updated_at=_datetime(item.get("updated")),
            deadline=(
                _datetime(item.get("deadline") or item.get("applicationDeadline") or item.get("validUntil"))
                or _explicit_deadline(description)
            ),
            source_status=_text(item.get("status")),
            raw=item,
        )


class MadridEmpleoSource(FeedJobSource):
    source_key = "madrid_empleo"
    source_name = "Madrid Empleo"
    feed_url = "https://datos.madrid.es/dataset/200033-0-oposiciones/resource/200033-0-oposiciones/download/200033-0-oposiciones.rss"

    def normalize_job(self, item: Any) -> NormalizedJob:
        job = super().normalize_job(item)
        searchable = f"{job.title} {job.description}".casefold()
        if any(term in searchable for term in ("relación de puestos de trabajo", "plantilla de personal", "oferta de empleo público anual", "plan de empleo")):
            raise ValueError("static workforce dataset is not an active vacancy")
        status = job.source_status
        if any(term in searchable for term in ("plazo cerrado", "plazo finalizado", "convocatoria cerrada")):
            status = "convocatoria cerrada"
        return NormalizedJob(**{**job.__dict__, "city": "Madrid", "region": "Comunidad de Madrid", "source_status": status})


class TecnoempleoSource(FeedJobSource):
    source_key = "tecnoempleo"
    source_name = "Tecnoempleo"

    def __init__(self, *, feed_url: str, **kwargs):
        super().__init__(**kwargs)
        if not feed_url:
            raise ValueError("Tecnoempleo requires an official RSS URL from Tecnoempleo")
        parsed = urlparse(feed_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Tecnoempleo RSS URL must use http or https")
        self.feed_url = feed_url


class DomestikaJobsSource(FeedJobSource):
    source_key = "domestika_jobs"
    source_name = "Domestika Jobs"
    feed_url = "https://www.domestika.org/es/jobs.atom"


class _EmpleoPublicoListingParser(HTMLParser):
    """Extract only official vacancy-detail links and their visible result text."""

    def __init__(self):
        super().__init__()
        self.rows: list[dict[str, str]] = []
        self._row: dict[str, Any] | None = None
        self._in_detail_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href") or ""
        match = re.search(r"detalleEmpleo\.htm\?[^\"']*idConvocatoria=(\d+)", href)
        if not match:
            return
        if self._row and self._row.get("external_id") == match.group(1):
            self._in_detail_link = True
            return
        self._finish_row()
        self._row = {"external_id": match.group(1), "url": href, "parts": []}
        self._in_detail_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a":
            self._in_detail_link = False

    def handle_data(self, data: str) -> None:
        if self._row is None:
            return
        value = _text(data)
        if not value:
            return
        if self._in_detail_link and not self._row.get("title"):
            self._row["title"] = value
        self._row["parts"].append(value)

    def close(self) -> None:
        super().close()
        self._finish_row()

    def _finish_row(self) -> None:
        if not self._row:
            return
        self._row["text"] = " ".join(self._row.pop("parts"))
        self.rows.append(self._row)
        self._row = None


class EmpleoPublicoSource(JobSourceAdapter):
    source_key = "empleo_publico"
    source_name = "Empleo Público"
    listing_url = "https://administracion.gob.es/pagFront/ofertasempleopublico/resultadosEmpleo.htm"

    def __init__(self, *, max_pages: int = 2, **kwargs):
        super().__init__(**kwargs)
        self.max_pages = min(10, max(1, int(max_pages)))

    def _fetch_sync(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        page_size = min(50, self.max_items)
        for page in range(self.max_pages):
            query = urlencode({
                "idioma": "es",
                "tipoPlazo": "1",
                "orders": "id",
                "sort": "desc",
                "tam": page_size,
                "desde": page * page_size + 1,
            })
            payload = self._read(f"{self.listing_url}?{query}")
            parser = _EmpleoPublicoListingParser()
            parser.feed(payload.decode("utf-8", errors="replace"))
            parser.close()
            for row in parser.rows:
                if row["external_id"] in seen:
                    continue
                seen.add(row["external_id"])
                rows.append(row)
                if len(rows) >= self.max_items:
                    return rows
            if len(parser.rows) < page_size:
                break
        return rows

    @staticmethod
    def _field(text: str, label: str, following_labels: tuple[str, ...]) -> str | None:
        boundary = "|".join(re.escape(value) for value in following_labels)
        match = re.search(
            rf"{re.escape(label)}\s*:?\s*(.+?)(?=\s+(?:{boundary})\s*:|$)",
            text,
            re.IGNORECASE,
        )
        return _text(match.group(1)) if match else None

    def normalize_job(self, item: Any) -> NormalizedJob:
        if not isinstance(item, dict):
            raise ValueError("Empleo Público item must be a dictionary")
        external_id = _text(item.get("external_id"))
        title = _text(item.get("title"))
        relative_url = _text(item.get("url"))
        text = _text(item.get("text")) or ""
        if not external_id or not title or not relative_url:
            raise ValueError("Empleo Público result is missing reference, title, or URL")
        labels = ("Ref", "Plazas", "Fin de plazo", "Titulación", "Ubicación", "Órgano convocante")
        deadline_text = self._field(text, "Fin de plazo", labels)
        qualification = self._field(text, "Titulación", labels)
        location = self._field(text, "Ubicación", labels)
        employer = self._field(text, "Órgano convocante", labels)
        description = ". ".join(
            value for value in (
                title,
                f"Órgano convocante: {employer}" if employer else None,
                f"Ubicación: {location}" if location else None,
                f"Titulación: {qualification}" if qualification else None,
                f"Fin de plazo: {deadline_text}" if deadline_text else None,
            )
            if value
        )
        return NormalizedJob(
            external_id=external_id,
            title=title,
            description=description,
            url=urljoin(self.listing_url, relative_url),
            employer=employer,
            region=location,
            deadline=parse_source_datetime(deadline_text, end_of_day=True) if deadline_text else None,
            reference_number=external_id,
            source_status="plazo abierto",
            raw=item,
        )


class GreenhouseSpainSource(JobSourceAdapter):
    """Public Greenhouse Job Board API connector restricted to Spain vacancies."""

    api_root = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, *, source_key: str, source_name: str, board_token: str, **kwargs):
        super().__init__(**kwargs)
        self.source_key = source_key
        self.source_name = source_name
        self.board_token = board_token

    def _is_spain_location(self, location: str) -> bool:
        normalized = location.casefold().strip()
        if "spain" in normalized or "españa" in normalized or normalized.startswith("es -"):
            return True
        # 2K's dedicated Madrid board currently labels some concrete vacancies
        # simply "Madrid"; this exception is intentionally board-specific.
        return self.board_token == "2kmadrid" and normalized == "madrid"

    def _fetch_sync(self) -> list[dict[str, Any]]:
        payload = self._read(f"{self.api_root}/{self.board_token}/jobs?content=true")
        data = json.loads(payload.decode("utf-8"))
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError(f"{self.source_key} response does not contain a jobs list")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for job in jobs:
            if not isinstance(job, dict) or job.get("internal_job_id") is None:
                continue
            external_id = str(job.get("id") or "").strip()
            location = _text((job.get("location") or {}).get("name"))
            if (
                not external_id
                or external_id in seen
                or not location
                or not self._is_spain_location(location)
            ):
                continue
            seen.add(external_id)
            rows.append(job)
            if len(rows) >= self.max_items:
                break
        return rows

    def normalize_job(self, item: Any) -> NormalizedJob:
        if not isinstance(item, dict):
            raise ValueError("Greenhouse job must be a dictionary")
        external_id = _text(item.get("id"))
        title = _text(item.get("title"))
        url = _text(item.get("absolute_url"))
        description = _text(item.get("content"))
        location = _text((item.get("location") or {}).get("name"))
        if not external_id or not title or not url or not description or not location:
            raise ValueError("Greenhouse job is missing id, title, URL, description, or location")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"job-boards.greenhouse.io", "boards.greenhouse.io"}:
            raise ValueError("Greenhouse canonical URL is not on an approved public job-board host")
        departments = item.get("departments") or []
        category = _text(departments[0].get("name")) if departments and isinstance(departments[0], dict) else None
        return NormalizedJob(
            external_id=external_id,
            title=title,
            description=description,
            url=url,
            employer=self.source_name,
            region=location,
            updated_at=_datetime(item.get("updated_at")),
            category=category,
            application_url=url,
            raw=item,
        )


class InfoJobsSource(JobSourceAdapter):
    source_key = "infojobs"
    source_name = "InfoJobs"
    api_url = "https://api.infojobs.net/api/9/offer"

    def __init__(self, *, client_id: str, client_secret: str, keywords: str = "", provinces=None, page_size: int = 20, max_pages: int = 2, **kwargs):
        super().__init__(**kwargs)
        if not client_id or not client_secret:
            raise ValueError("InfoJobs client_id and client_secret are required")
        import base64
        self.authorization = "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self.keywords = _text(keywords) or ""
        self.provinces = tuple(value.strip() for value in (provinces or ()) if value.strip())
        self.page_size = min(50, max(10, int(page_size)))
        self.max_pages = min(10, max(1, int(max_pages)))

    def _fetch_sync(self) -> list[dict[str, Any]]:
        offers: list[dict[str, Any]] = []
        province_values = self.provinces or (None,)
        for province in province_values:
            for page in range(1, self.max_pages + 1):
                params = {"country": "espana", "maxResults": self.page_size, "page": page}
                if self.keywords:
                    params["q"] = self.keywords
                if province:
                    params["province"] = province
                payload = self._read(f"{self.api_url}?{urlencode(params)}", headers={"Authorization": self.authorization})
                data = json.loads(payload.decode("utf-8"))
                page_offers = list(data.get("offers") or data.get("items") or [])
                offers.extend(page_offers)
                total_pages = int(data.get("totalPages") or page)
                if not page_offers or page >= total_pages or len(offers) >= self.max_items:
                    break
            if len(offers) >= self.max_items:
                break
        return offers[: self.max_items]

    def normalize_job(self, item: Any) -> NormalizedJob:
        if not isinstance(item, dict):
            raise ValueError("InfoJobs item must be a dictionary")
        title = _text(item.get("title"))
        url = _text(item.get("link") or item.get("url"))
        description = _text(item.get("description") or item.get("requirementMin") or title)
        if not title or not url or not description:
            raise ValueError("InfoJobs job is missing title, URL, or description")
        province = item.get("province") or {}
        city = item.get("city") or {}
        author = item.get("author") or {}
        return NormalizedJob(
            external_id=str(item.get("id") or url), title=title, description=description, url=url,
            employer=_text(author.get("name") if isinstance(author, dict) else author),
            city=_text(city.get("value") if isinstance(city, dict) else city),
            region=_text(province.get("value") if isinstance(province, dict) else province),
            salary=_text(item.get("salaryDescription")), contract_type=_text((item.get("contractType") or {}).get("value") if isinstance(item.get("contractType"), dict) else item.get("contractType")),
            working_hours=_text((item.get("workDay") or {}).get("value") if isinstance(item.get("workDay"), dict) else item.get("workDay")),
            published_at=_datetime(item.get("published")), updated_at=_datetime(item.get("updated")),
            deadline=_datetime(item.get("applicationDeadline") or item.get("deadline")),
            experience=_text((item.get("experienceMin") or {}).get("value") if isinstance(item.get("experienceMin"), dict) else item.get("experienceMin")),
            education=_text((item.get("study") or {}).get("value") if isinstance(item.get("study"), dict) else item.get("study")),
            category=_text((item.get("category") or {}).get("value") if isinstance(item.get("category"), dict) else item.get("category")),
            subcategory=_text((item.get("subcategory") or {}).get("value") if isinstance(item.get("subcategory"), dict) else item.get("subcategory")),
            source_status=_text(item.get("status")), remote=bool(item.get("teleworking")) if item.get("teleworking") is not None else None,
            application_url=_text(item.get("applicationUrl") or url), raw=item,
        )
