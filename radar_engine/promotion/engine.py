from __future__ import annotations

import logging

from radar_engine.promotion.mapper import map_approved_source_to_radar_item, validate_mapped_payload
from radar_engine.promotion.models import PromotionReport, PromotionResult


logger = logging.getLogger(__name__)


class RadarPromotionEngine:
    def __init__(self, loader=None, promoter=None):
        if loader is None or promoter is None:
            from radar_engine.promotion.storage import load_approved_unpromoted_candidates, promote_candidate

            loader = loader or load_approved_unpromoted_candidates
            promoter = promoter or promote_candidate
        self.loader = loader
        self.promoter = promoter

    def run(
        self,
        limit: int = 50,
        candidate_id: str | None = None,
        dry_run: bool = False,
        promoted_by: int | None = None,
    ) -> PromotionReport:
        safe_limit = max(1, min(int(limit), 200))
        report = PromotionReport()
        sources = self.loader(limit=safe_limit, candidate_id=candidate_id)
        report.loaded = len(sources)
        for source in sources:
            report.processed += 1
            try:
                if source.already_promoted:
                    report.already_promoted += 1
                    continue
                payload = map_approved_source_to_radar_item(source)
                errors = validate_mapped_payload(payload)
                if errors:
                    report.rejected += 1
                    report.errors.append(f"{source.candidate_id}: {errors}")
                    continue
                if dry_run:
                    report.created += 1
                    continue
                result: PromotionResult = self.promoter(source, promoted_by=promoted_by)
                if result.created:
                    report.created += 1
                elif result.already_promoted:
                    report.already_promoted += 1
                elif result.status == "rejected":
                    report.rejected += 1
                    report.errors.append(f"{source.candidate_id}: {result.errors}")
                else:
                    report.failed += 1
                    report.errors.append(f"{source.candidate_id}: unexpected status {result.status}")
            except Exception as error:
                logger.exception("Radar promotion failed for candidate %s", source.candidate_id)
                report.failed += 1
                report.errors.append(f"{source.candidate_id}: {error}")
        return report
