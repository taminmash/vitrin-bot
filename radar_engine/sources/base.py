from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from radar_engine.models import RawRadarItem


logger = logging.getLogger(__name__)


class BaseRadarSource(ABC):
    source_key: str
    source_name: str

    @abstractmethod
    async def fetch(self) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_item: Any) -> RawRadarItem:
        raise NotImplementedError

    async def fetch_normalized(self) -> list[RawRadarItem]:
        raw_items = await self.fetch()
        normalized: list[RawRadarItem] = []
        for index, raw_item in enumerate(raw_items):
            try:
                normalized.append(self.normalize(raw_item))
            except Exception as error:
                logger.exception(
                    "Skipping malformed %s item at index %s: %s",
                    self.source_key,
                    index,
                    error,
                )
        return normalized
