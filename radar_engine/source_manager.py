from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable

from radar_engine.models import RawRadarItem
from radar_engine.sources.base import BaseRadarSource
from radar_engine.sources.boe import BOESource
from radar_engine.storage import StoreResult, store_raw_item


logger = logging.getLogger(__name__)


@dataclass
class IngestionReport:
    source_key: str
    fetched_count: int = 0
    normalized_count: int = 0
    inserted_count: int = 0
    duplicate_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    errors: list[str] = field(default_factory=list)


StoreFunction = Callable[[RawRadarItem], StoreResult]


class SourceManager:
    def __init__(self, store_func: StoreFunction = store_raw_item):
        self._sources: dict[str, BaseRadarSource] = {}
        self._store_func = store_func

    def register(self, source: BaseRadarSource) -> None:
        if source.source_key in self._sources:
            raise ValueError(f"Source already registered: {source.source_key}")
        self._sources[source.source_key] = source

    def get_source(self, source_key: str) -> BaseRadarSource:
        try:
            return self._sources[source_key]
        except KeyError as error:
            raise KeyError(f"Unknown Radar source: {source_key}") from error

    async def ingest_source(self, source_key: str) -> IngestionReport:
        source = self.get_source(source_key)
        report = IngestionReport(source_key=source_key)

        try:
            raw_items = await source.fetch()
        except Exception as error:
            logger.exception("Radar source fetch failed for %s", source_key)
            report.errors.append(f"fetch failed: {error}")
            report.failed_count += 1
            return report

        report.fetched_count = len(raw_items)
        normalized: list[RawRadarItem] = []
        for index, raw_item in enumerate(raw_items):
            try:
                normalized.append(source.normalize(raw_item))
            except Exception as error:
                logger.exception("Radar source normalization failed for %s item %s", source_key, index)
                report.failed_count += 1
                report.errors.append(f"normalize item {index}: {error}")

        report.normalized_count = len(normalized)
        for item in normalized:
            try:
                result = self._store_func(item)
            except Exception as error:
                logger.exception("Radar raw item storage failed for %s/%s", item.source_key, item.external_id)
                report.failed_count += 1
                report.errors.append(f"store {item.external_id or item.source_url}: {error}")
                continue

            if result.status == "inserted":
                report.inserted_count += 1
            elif result.status == "duplicate":
                report.duplicate_count += 1
            elif result.status == "updated":
                report.updated_count += 1
            else:
                report.failed_count += 1
                report.errors.append(f"unknown store status: {result.status}")

        return report


def build_default_source_manager() -> SourceManager:
    manager = SourceManager()
    manager.register(BOESource())
    return manager
