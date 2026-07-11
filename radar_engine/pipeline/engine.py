from __future__ import annotations

from dataclasses import dataclass, field
import logging

from radar_engine.pipeline.enricher import PIPELINE_VERSION, enrich_candidate
from radar_engine.pipeline.normalizer import normalize_raw_item
from radar_engine.pipeline.storage import (
    load_pending_raw_items,
    load_source_info,
    mark_raw_failed,
    mark_raw_rejected,
    store_candidate,
)
from radar_engine.pipeline.validator import validate_candidate


logger = logging.getLogger(__name__)


@dataclass
class PipelineReport:
    loaded_count: int = 0
    processed_count: int = 0
    created_count: int = 0
    already_exists_count: int = 0
    rejected_count: int = 0
    failed_count: int = 0
    errors: list[str] = field(default_factory=list)


class RadarCandidatePipeline:
    def __init__(
        self,
        load_raw_items=load_pending_raw_items,
        load_source=load_source_info,
        store_valid=store_candidate,
        store_rejected=mark_raw_rejected,
        mark_failed=mark_raw_failed,
    ):
        self.load_raw_items = load_raw_items
        self.load_source = load_source
        self.store_valid = store_valid
        self.store_rejected = store_rejected
        self.mark_failed = mark_failed

    def run(self, limit: int = 100) -> PipelineReport:
        safe_limit = max(1, min(int(limit), 500))
        report = PipelineReport()
        raw_items = self.load_raw_items(safe_limit)
        report.loaded_count = len(raw_items)

        for raw_item in raw_items:
            try:
                source_info = self.load_source(raw_item.source_key)
                if not source_info:
                    raise ValueError(f"Missing source registry entry for {raw_item.source_key}")
                candidate = enrich_candidate(normalize_raw_item(raw_item, source_info))
                validation = validate_candidate(candidate)
                if validation.is_valid:
                    result = self.store_valid(candidate, validation, PIPELINE_VERSION)
                else:
                    candidate.candidate_status = "rejected"
                    result = self.store_rejected(candidate, validation, PIPELINE_VERSION)

                report.processed_count += 1
                if result.status == "created":
                    report.created_count += 1
                elif result.status == "already_exists":
                    report.already_exists_count += 1
                elif result.status == "rejected":
                    report.rejected_count += 1
                else:
                    report.failed_count += 1
                    report.errors.append(f"{raw_item.id}: store returned {result.status}")
            except Exception as error:
                logger.exception("Radar candidate pipeline failed for raw item %s", getattr(raw_item, "id", "-"))
                report.failed_count += 1
                report.errors.append(f"{getattr(raw_item, 'id', '-')}: {error}")
                try:
                    self.mark_failed(raw_item.id, str(error))
                except Exception:
                    logger.exception("Could not mark raw item %s as candidate_failed", getattr(raw_item, "id", "-"))

        return report
