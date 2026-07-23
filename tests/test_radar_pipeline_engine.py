import unittest

from radar_engine.pipeline.candidate import SourceInfo, StoredRawRadarItem
from radar_engine.pipeline.engine import RadarCandidatePipeline
from radar_engine.pipeline.storage import CandidateStoreResult


def raw(raw_id, title="Nuevo plazo de residencia", body="Cambio de extranjeria con plazo de solicitud para residencia."):
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

    def test_blank_title_and_body_are_rejected_not_failed(self):
        items = [raw("blank-title", title=" ", body="Valid body text"), raw("blank-body", title="Valid title", body=" ")]
        rejected = []
        failed = []

        def store_rejected(candidate, validation, version):
            rejected.append((candidate.raw_item_id, validation.as_dicts()))
            return CandidateStoreResult("rejected", f"c-{candidate.raw_item_id}", candidate.raw_item_id)

        pipeline = RadarCandidatePipeline(
            load_raw_items=lambda limit: items,
            load_source=lambda source_key: SourceInfo("boe", "BOE", "Government", "official", 5),
            store_valid=lambda candidate, validation, version: CandidateStoreResult("created", "c", candidate.raw_item_id),
            store_rejected=store_rejected,
            mark_failed=lambda raw_id, error: failed.append(raw_id) or CandidateStoreResult("failed", None, raw_id),
        )
        report = pipeline.run()
        self.assertEqual(report.rejected_count, 2)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(failed, [])
        self.assertEqual([item[0] for item in rejected], ["blank-title", "blank-body"])
        self.assertIn({"field": "title", "code": "blank", "message": "Title must not be blank."}, rejected[0][1])
        self.assertIn({"field": "body", "code": "blank", "message": "Body must not be blank."}, rejected[1][1])

    def test_short_title_and_body_are_structured_rejections(self):
        captured = []
        pipeline = RadarCandidatePipeline(
            load_raw_items=lambda limit: [raw("short", title="abcd", body="short")],
            load_source=lambda source_key: SourceInfo("boe", "BOE", "Government", "official", 5),
            store_valid=lambda candidate, validation, version: CandidateStoreResult("created", "c", candidate.raw_item_id),
            store_rejected=lambda candidate, validation, version: captured.extend(validation.as_dicts())
            or CandidateStoreResult("rejected", "c-short", candidate.raw_item_id),
            mark_failed=lambda raw_id, error: CandidateStoreResult("failed", None, raw_id),
        )
        report = pipeline.run()
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.failed_count, 0)
        issue_codes = {(issue["field"], issue["code"]) for issue in captured}
        self.assertIn(("title", "too_short"), issue_codes)
        self.assertIn(("body", "too_short"), issue_codes)

    def test_low_actionability_candidate_is_rejected_not_sent_to_ai(self):
        captured = []
        pipeline = RadarCandidatePipeline(
            load_raw_items=lambda limit: [raw("ceremony", title="Acto institucional", body="Ceremonia y entrega de premios del ministerio.")],
            load_source=lambda source_key: SourceInfo("boe", "BOE", "Government", "official", 5),
            store_valid=lambda candidate, validation, version: CandidateStoreResult("created", "c", candidate.raw_item_id),
            store_rejected=lambda candidate, validation, version: captured.append((candidate, validation.as_dicts()))
            or CandidateStoreResult("rejected", "c-ceremony", candidate.raw_item_id),
            mark_failed=lambda raw_id, error: CandidateStoreResult("failed", None, raw_id),
        )
        report = pipeline.run()
        self.assertEqual(report.created_count, 0)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.failed_count, 0)
        candidate, issues = captured[0]
        self.assertEqual(candidate.metadata["rejection_reason"], "ceremonial_event")
        self.assertFalse(candidate.metadata["actionability_gate"]["passed"])
        self.assertIn(
            {
                "field": "actionability",
                "code": "ceremonial_event",
                "message": "Candidate does not meet Radar actionability requirements.",
            },
            issues,
        )

    def test_madrid_normalized_job_reaches_shared_candidate_pipeline(self):
        item = raw(
            "madrid-job",
            title="Desarrollador Backend",
            body="Construccion de servicios distribuidos para una empresa internacional.",
        )
        item.source_key = "madrid_empleo"
        item.source_name = "Madrid Empleo"
        item.metadata = {"content_type": "job"}
        stored = []
        pipeline = RadarCandidatePipeline(
            load_raw_items=lambda limit: [item],
            load_source=lambda source_key: SourceInfo(
                "madrid_empleo", "Madrid Empleo", "Jobs", "official", 5, city="Madrid"
            ),
            store_valid=lambda candidate, validation, version: stored.append(candidate)
            or CandidateStoreResult("created", "candidate-job", candidate.raw_item_id),
            store_rejected=lambda candidate, validation, version: self.fail("job was rejected"),
        )
        report = pipeline.run()
        self.assertEqual(report.created_count, 1)
        self.assertEqual(stored[0].metadata["actionability_gate"]["matched_signals"], ["work_opportunity"])
