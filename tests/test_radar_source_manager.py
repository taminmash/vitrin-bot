import unittest

from radar_engine.models import RawRadarItem
from radar_engine.source_manager import SourceManager, build_default_source_manager
from radar_engine.sources.base import BaseRadarSource
from radar_engine.storage import StoreResult


def item(external_id):
    return RawRadarItem(
        source_key="mock",
        external_id=external_id,
        source_name="Mock",
        source_url=f"https://example.com/{external_id}",
        original_title=f"Title {external_id}",
        original_text="Body",
        original_language="es",
        published_at=None,
        valid_from=None,
        valid_until=None,
        raw_category=None,
        raw_location=None,
        metadata={},
    )


class MockSource(BaseRadarSource):
    source_key = "mock"
    source_name = "Mock"

    async def fetch(self):
        return ["insert", "duplicate", "updated", "bad", "store_fail"]

    def normalize(self, raw_item):
        if raw_item == "bad":
            raise ValueError("bad item")
        return item(raw_item)


class SourceManagerTests(unittest.IsolatedAsyncioTestCase):
    def test_default_manager_registers_boe(self):
        manager = build_default_source_manager()
        self.assertEqual(manager.get_source("boe").source_name, "BOE")

    def test_register_duplicate_and_unknown_source(self):
        manager = SourceManager()
        manager.register(MockSource())
        with self.assertRaises(ValueError):
            manager.register(MockSource())
        with self.assertRaises(KeyError):
            manager.get_source("unknown")

    async def test_ingestion_report_counts_item_failures(self):
        def store(raw_item):
            if raw_item.external_id == "insert":
                return StoreResult("inserted", "1", "k1")
            if raw_item.external_id == "duplicate":
                return StoreResult("duplicate", "2", "k2")
            if raw_item.external_id == "updated":
                return StoreResult("updated", "3", "k3")
            raise RuntimeError("store failed")

        manager = SourceManager(store_func=store)
        manager.register(MockSource())
        report = await manager.ingest_source("mock")
        self.assertEqual(report.fetched_count, 5)
        self.assertEqual(report.normalized_count, 4)
        self.assertEqual(report.inserted_count, 1)
        self.assertEqual(report.duplicate_count, 1)
        self.assertEqual(report.updated_count, 1)
        self.assertEqual(report.failed_count, 2)
