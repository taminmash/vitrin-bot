from __future__ import annotations

from dataclasses import dataclass, field
import logging

from radar_engine.classification.classifier import RadarAIClassifier


logger = logging.getLogger(__name__)


@dataclass
class ClassificationReport:
    loaded: int = 0
    processed: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class RadarClassificationEngine:
    def __init__(
        self,
        classifier: RadarAIClassifier | None = None,
        load_candidates=None,
        store_result=None,
    ):
        from radar_engine.classification.storage import (
            load_pending_classification_candidates,
            store_classification_result,
        )

        self.classifier = classifier or RadarAIClassifier()
        self.load_candidates = load_candidates or load_pending_classification_candidates
        self.store_result = store_result or store_classification_result

    def run(
        self,
        limit: int = 50,
        candidate_id: str | None = None,
        dry_run: bool = False,
    ) -> ClassificationReport:
        safe_limit = max(1, min(int(limit), 200))
        sources = self.load_candidates(limit=safe_limit, candidate_id=candidate_id)
        report = ClassificationReport(loaded=len(sources))
        for source in sources:
            try:
                result = self.classifier.classify(source)
                report.processed += 1
                if dry_run:
                    report.skipped += 1
                    continue
                self.store_result(result, source.ai_result_id)
                report.completed += 1
            except Exception as error:
                logger.exception(
                    "Radar classification failed for candidate %s",
                    getattr(source, "candidate_id", "-"),
                )
                report.failed += 1
                report.errors.append(f"{getattr(source, 'candidate_id', '-')}: {error}")
        return report
