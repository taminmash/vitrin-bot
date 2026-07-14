from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time

from radar_engine.ai.providers import AIQuotaError
from radar_engine.classification.classifier import RadarAIClassifier


logger = logging.getLogger(__name__)


@dataclass
class ClassificationReport:
    loaded: int = 0
    processed: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    remaining: int = 0
    rate_limited: int = 0
    stopped_early: bool = False
    errors: list[str] = field(default_factory=list)


class RadarClassificationEngine:
    def __init__(
        self,
        classifier: RadarAIClassifier | None = None,
        load_candidates=None,
        store_result=None,
        request_delay_seconds: float = 0.0,
    ):
        from radar_engine.classification.storage import (
            load_pending_classification_candidates,
            store_classification_result,
        )

        self.classifier = classifier or RadarAIClassifier()
        self.load_candidates = load_candidates or load_pending_classification_candidates
        self.store_result = store_result or store_classification_result
        self.request_delay_seconds = max(0.0, float(request_delay_seconds))

    def run(
        self,
        limit: int = 50,
        candidate_id: str | None = None,
        dry_run: bool = False,
    ) -> ClassificationReport:
        safe_limit = max(1, min(int(limit), 200))
        sources = self.load_candidates(limit=safe_limit, candidate_id=candidate_id)
        report = ClassificationReport(loaded=len(sources))
        for index, source in enumerate(sources):
            try:
                report.processed += 1
                result = self.classifier.classify(source)
                if dry_run:
                    report.skipped += 1
                    continue
                self.store_result(result, source.ai_result_id)
                report.completed += 1
            except AIQuotaError as error:
                logger.warning("Gemini rate limit reached. Remaining AI jobs postponed to next cycle.")
                report.rate_limited += 1
                report.stopped_early = True
                report.remaining = len(sources) - index
                report.errors.append(str(error))
                break
            except Exception as error:
                logger.exception(
                    "Radar classification failed for candidate %s",
                    getattr(source, "candidate_id", "-"),
                )
                report.failed += 1
                report.errors.append(f"{getattr(source, 'candidate_id', '-')}: {error}")
            if self.request_delay_seconds and index < len(sources) - 1:
                time.sleep(self.request_delay_seconds)
        if not report.stopped_early:
            report.remaining = 0
        return report
