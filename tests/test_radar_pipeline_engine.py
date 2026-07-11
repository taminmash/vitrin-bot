import unittest

from radar_engine.pipeline.candidate import SourceInfo, StoredRawRadarItem
from radar_engine.pipeline.engine import RadarCandidatePipeline
from radar_engine.pipeline.storage import CandidateStoreResult


def raw(raw_id, title="Valid title", body="Valid body text"):
    return StoredRawRadarItem(
        id=raw_id,
        source_key="boe",
        external_id=f"BOE-{raw_id}",
        source_name="BOE",
        source_url=f"https://www.boe.es/{raw_id}",
        canonical_url=None,
        original_title=title,
        original_text=body,
        original_language="es",
        published_at=None,
        valid_from=None,
        valid_until=None,
        raw_category=None,
        raw_location=None,
        metadata={},
    )


class PipelineEngineTests(unittest.TestCase):
    def test_report_counters_and_item_isolation(self):
        items = [raw("1"), raw("2"), raw("3", title="bad", body="tiny"), raw("4"), raw("5")]

        def load_raw(limit):
            self.assertEqual(limit, 4)
            return items[:limit]

        def load_source(source_key):
            if source_key == "missing":
                return None
            return SourceInfo("boe", "BOE", "Government", "official", 5)

        def store_valid(candidate, validation, version):
            if candidate.raw_item_id == "2":
                return CandidateStoreResult("already_exists", "c2", candidate.raw_item_id)
            if candidate.raw_item_id == "4":
                raise RuntimeError("store failed")
            return CandidateStoreResult("created", "c1", candidate.raw_item_id)

        failed = []
        pipeline = RadarCandidatePipeline(
            load_raw_items=load_raw,
            load_source=load_source,
            store_valid=store_valid,
            store_rejected=lambda candidate, validation, version: CandidateStoreResult("rejected", "c3", candidate.raw_item_id),
            mark_failed=lambda raw_id, error: failed.append(raw_id) or CandidateStoreResult("failed", None, raw_id),
        )
        report = pipeline.run(limit=4)
        self.assertEqual(report.loaded_count, 4)
        self.assertEqual(report.processed_count, 3)
        self.assertEqual(report.created_count, 1)
        self.assertEqual(report.already_exists_count, 1)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.failed_count, 1)
        self.assertEqual(failed, ["4"])

    def test_missing_source_registry_affects_only_item(self):
        items = [raw("1"), raw("2")]
        items[0].source_key = "missing"
        pipeline = RadarCandidatePipeline(
            load_raw_items=lambda limit: items,
            load_source=lambda source_key: None if source_key == "missing" else SourceInfo("boe", "BOE", "Government", "official", 5),
            store_valid=lambda candidate, validation, version: CandidateStoreResult("created", "c", candidate.raw_item_id),
            mark_failed=lambda raw_id, error: CandidateStoreResult("failed", None, raw_id),
        )
        report = pipeline.run()
        self.assertEqual(report.failed_count, 1)
        self.assertEqual(report.created_count, 1)
