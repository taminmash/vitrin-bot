from __future__ import annotations

from radar_engine.review.models import ReviewQueueReport


class RadarReviewEngine:
    def __init__(self, load_queue=None, status_report=None):
        from radar_engine.review.storage import load_review_queue, review_status_report

        self.load_queue = load_queue or load_review_queue
        self.status_report = status_report or review_status_report

    def queue_report(self, limit: int = 50, candidate_id: str | None = None) -> ReviewQueueReport:
        safe_limit = max(1, min(int(limit), 200))
        report = self.status_report()
        queue = self.load_queue(limit=safe_limit, candidate_id=candidate_id)
        report.pending = len(queue) if candidate_id else report.pending
        return report
