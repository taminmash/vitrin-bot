from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

from radar_engine.models import RawRadarItem
from radar_engine.sources.base import BaseRadarSource


logger = logging.getLogger(__name__)


BOE_DAILY_XML_URL = "https://www.boe.es/boe/dias/{year}/{month}/{day}/sumario.xml"
BOE_BASE_URL = "https://www.boe.es/"
BOE_LOOKBACK_ENV = "BOE_LOOKBACK_DAYS"
DEFAULT_LOOKBACK_DAYS = 7
MIN_LOOKBACK_DAYS = 1
MAX_LOOKBACK_DAYS = 30
MADRID_TZ = ZoneInfo("Europe/Madrid")
USER_AGENT = "VitrinSpainRadar/1.0"


class BOENoEditionError(Exception):
    """Raised when BOE has no daily summary for a specific date."""


class BOERequestError(Exception):
    """Raised for network/system failures while requesting BOE."""


class BOEXMLValidationError(Exception):
    """Raised when BOE returns non-XML or an unexpected XML document."""


@dataclass
class BOERawEntry:
    element: ET.Element
    issue_date: datetime | None
    section: str | None


class BOESource(BaseRadarSource):
    """Experimental BOE connector using BOE's official daily summary XML.

    Official endpoint pattern:
    https://www.boe.es/boe/dias/YYYY/MM/DD/sumario.xml
    """

    source_key = "boe"
    source_name = "BOE"

    def __init__(self, days_back: int | None = None, max_items: int = 50, timeout_seconds: int = 12):
        self.days_back = self._normalize_lookback(days_back)
        self.max_items = max(1, max_items)
        self.timeout_seconds = max(1, timeout_seconds)

    async def fetch(self) -> list[BOERawEntry]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[BOERawEntry]:
        entries: list[BOERawEntry] = []
        attempted_count = 0
        fetched_count = 0
        no_edition_count = 0
        errors: list[str] = []
        today = datetime.now(MADRID_TZ).date()
        for offset in range(self.days_back):
            date_value = today - timedelta(days=offset)
            url = self._daily_xml_url(date_value)
            attempted_count += 1
            try:
                payload = self._read_url(url)
                entries.extend(self.parse_xml(payload))
                fetched_count += 1
                logger.info("Fetched BOE daily summary XML for %s", date_value.isoformat())
                break
            except BOENoEditionError as error:
                no_edition_count += 1
                logger.info("No BOE daily XML edition for %s: %s", date_value.isoformat(), error)
            except Exception as error:
                errors.append(f"{date_value.isoformat()}: {error}")
                logger.warning("Could not fetch BOE XML for %s: %s", date_value.isoformat(), error)
            if len(entries) >= self.max_items:
                break
        if attempted_count and fetched_count == 0:
            if no_edition_count == attempted_count:
                logger.info(
                    "No BOE daily XML edition found in the last %s day(s).",
                    self.days_back,
                )
                return []
            if no_edition_count and not errors:
                return []
            raise RuntimeError(
                f"BOE fetch failed for all attempted daily XML documents "
                f"(attempted={attempted_count}; first_error={errors[0] if errors else 'unknown'})"
            )
        return entries[: self.max_items]

    def _read_url(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                payload = response.read()
        except HTTPError as error:
            if error.code in {400, 404}:
                raise BOENoEditionError(f"HTTP {error.code}") from error
            raise BOERequestError(f"HTTP {error.code}") from error
        except TimeoutError as error:
            raise BOERequestError("timeout") from error
        except URLError as error:
            raise BOERequestError(str(error.reason)) from error
        except OSError as error:
            raise BOERequestError(str(error)) from error
        self._validate_xml_payload(payload, content_type)
        return payload

    def parse_xml(self, xml_payload: bytes | str) -> list[BOERawEntry]:
        root = self._parse_xml_root(xml_payload)
        issue_date = self._issue_date(root)
        entries: list[BOERawEntry] = []
        for section in root.findall(".//seccion"):
            section_name = section.attrib.get("nombre") or section.attrib.get("num")
            for item in section.findall(".//item"):
                entries.append(BOERawEntry(item, issue_date, section_name))
        if not entries:
            for item in root.findall(".//item"):
                entries.append(BOERawEntry(item, issue_date, None))
        return entries[: self.max_items]

    def _daily_xml_url(self, date_value) -> str:
        return BOE_DAILY_XML_URL.format(
            year=date_value.strftime("%Y"),
            month=date_value.strftime("%m"),
            day=date_value.strftime("%d"),
        )

    def _normalize_lookback(self, days_back: int | None) -> int:
        if days_back is None:
            raw_value = os.getenv(BOE_LOOKBACK_ENV, str(DEFAULT_LOOKBACK_DAYS))
            try:
                days_back = int(raw_value)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid %s=%r; using default %s",
                    BOE_LOOKBACK_ENV,
                    raw_value,
                    DEFAULT_LOOKBACK_DAYS,
                )
                days_back = DEFAULT_LOOKBACK_DAYS
        return min(MAX_LOOKBACK_DAYS, max(MIN_LOOKBACK_DAYS, int(days_back)))

    def _validate_xml_payload(self, payload: bytes, content_type: str) -> None:
        lowered_type = (content_type or "").lower()
        leading = payload.lstrip()[:80].lower()
        if b"<html" in leading or "html" in lowered_type:
            raise BOEXMLValidationError("BOE returned an HTML document instead of XML")
        if "xml" not in lowered_type and not leading.startswith(b"<?xml") and not leading.startswith(b"<sumario"):
            raise BOEXMLValidationError(f"unexpected BOE content type: {content_type or 'unknown'}")
        self._parse_xml_root(payload)

    def _parse_xml_root(self, xml_payload: bytes | str) -> ET.Element:
        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError as error:
            raise BOEXMLValidationError(f"malformed BOE XML: {error}") from error
        if self._local_name(root.tag) != "sumario":
            raise BOEXMLValidationError(f"unexpected BOE XML root: {root.tag}")
        if root.find(".//diario") is None:
            raise BOEXMLValidationError("BOE summary XML is missing diario")
        return root

    def _local_name(self, tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def normalize(self, raw_item: Any) -> RawRadarItem:
        if not isinstance(raw_item, BOERawEntry):
            raise ValueError("BOE raw item must be BOERawEntry")
        item = raw_item.element
        external_id = item.attrib.get("id") or self._text(item, "identificador") or self._text(item, "guid")
        title = self._text(item, "titulo") or self._text(item, "title")
        url = (
            self._text(item, "urlXml")
            or self._text(item, "urlHtm")
            or self._text(item, "urlHtml")
            or self._text(item, "link")
            or self._text(item, "urlPdf")
        )
        if not external_id:
            external_id = self._external_id_from_url(url)
        official_url = self._document_url(url, external_id)
        if not external_id and not official_url:
            raise ValueError("BOE item is missing both external identifier and document URL")
        if not official_url:
            raise ValueError(f"BOE item {external_id or '-'} is missing a document-specific official URL")
        description = (
            self._text(item, "texto")
            or self._text(item, "descripcion")
            or self._text(item, "description")
            or title
        )
        published_at = self._published_at(item, raw_item.issue_date)
        metadata = {
            "boe_id": external_id,
            "section": raw_item.section,
            "department": self._ancestor_text(item, "departamento"),
            "url_pdf": self._absolute(self._text(item, "urlPdf")),
            "url_html": self._absolute(self._text(item, "urlHtm") or self._text(item, "urlHtml")),
            "url_xml": self._absolute(self._text(item, "urlXml")),
        }
        return RawRadarItem(
            source_key=self.source_key,
            external_id=external_id or "",
            source_name=self.source_name,
            source_url=official_url,
            canonical_url=official_url,
            original_title=title or "",
            original_text=description or "",
            original_language="es",
            published_at=published_at,
            valid_from=published_at,
            valid_until=None,
            raw_category=raw_item.section,
            raw_location="Spain",
            metadata={key: value for key, value in metadata.items() if value},
        )

    def _issue_date(self, root: ET.Element) -> datetime | None:
        for value in (root.attrib.get("fecha"), self._text(root, "fecha")):
            parsed = self._parse_date(value)
            if parsed:
                return parsed
        diario = root.find(".//diario")
        if diario is not None:
            return self._parse_date(diario.attrib.get("fecha"))
        return None

    def _published_at(self, item: ET.Element, fallback: datetime | None) -> datetime | None:
        for tag in ("pubDate", "fecha", "fechaPublicacion"):
            parsed = self._parse_date(self._text(item, tag))
            if parsed:
                return parsed
        return fallback

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        text = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        try:
            parsed = parsedate_to_datetime(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _text(self, element: ET.Element, tag: str) -> str | None:
        child = element.find(tag)
        if child is None or child.text is None:
            return None
        return child.text.strip() or None

    def _ancestor_text(self, element: ET.Element, tag: str) -> str | None:
        return element.attrib.get(tag)

    def _absolute(self, url: str | None) -> str | None:
        return urljoin(BOE_BASE_URL, url) if url else None

    def _external_id_from_url(self, url: str | None) -> str | None:
        if not url:
            return None
        query = parse_qs(urlsplit(urljoin(BOE_BASE_URL, url)).query)
        values = query.get("id") or []
        if values and values[0].startswith("BOE-"):
            return values[0]
        return None

    def _document_url(self, url: str | None, external_id: str | None) -> str | None:
        if url:
            absolute = urljoin(BOE_BASE_URL, url)
            parsed = urlsplit(absolute)
            hostname = parsed.hostname or ""
            if (hostname == "boe.es" or hostname.endswith(".boe.es")) and parsed.path.strip("/"):
                if absolute.rstrip("/") != BOE_BASE_URL.rstrip("/"):
                    return absolute
        if external_id and external_id.startswith("BOE-"):
            return urljoin(BOE_BASE_URL, f"diario_boe/txt.php?id={external_id}")
        return None
