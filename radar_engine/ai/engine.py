from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time

from radar_engine.ai.summarizer import RadarAISummarizer


logger = logging.getLogger(__name__)


@dataclass
class AIReport:
    loaded: int = 0
    processed: int = 0
    completed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class RadarAIEngine:
    def __init__(
        self,
        summarizer: RadarAISummarizer | None = None,
        load_candidates=None,
        store_result=None,
        mark_failed=None,
        request_delay_seconds: float = 0.0,
    ):
        from radar_engine.ai.storage import load_pending_ai_candidates, store_ai_result

        self.summarizer = summarizer or RadarAISummarizer()
        self.load_candidates = load_candidates or load_pending_ai_candidates
        self.store_result = store_result or store_ai_result
        self.mark_failed = mark_failed
        self.request_delay_seconds = max(0.0, float(request_delay_seconds))

    def run(self, limit: int = 50, candidate_id: str | None = None, dry_run: bool = False) -> AIReport:
        safe_limit = max(1, min(int(limit), 200))
        candidates = self.load_candidates(limit=safe_limit, candidate_id=candidate_id)
        report = AIReport(loaded=len(candidates))
        for index, item in enumerate(candidates):
            try:
                result = self.summarizer.summarize(item.candidate)
                report.processed += 1
                if dry_run:
                    report.completed += 1
                    continue
                self.store_result(item.candidate_id, result)
                report.completed += 1
            except Exception as error:
                logger.exception("Radar AI processing failed for candidate %s", getattr(item, "candidate_id", "-"))
                report.failed += 1
                report.errors.append(f"{getattr(item, 'candidate_id', '-')}: {error}")
                if self.mark_failed and not dry_run:
                    try:
                        self.mark_failed(getattr(item, "candidate_id", None), str(error))
                    except Exception:
                        logger.exception("Could not mark candidate %s as failed", getattr(item, "candidate_id", "-"))
            if self.request_delay_seconds and index < len(candidates) - 1:
                time.sleep(self.request_delay_seconds)
        return report
