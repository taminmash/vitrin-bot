from __future__ import annotations

import time

from radar_engine.ai.client import AIClient
from radar_engine.ai.models import AITaskResult
from radar_engine.ai.prompts import PROMPT_VERSION, build_summary_prompt
from radar_engine.pipeline.candidate import RadarCandidate


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "short_summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["headline", "short_summary", "why_it_matters", "confidence"],
}


class RadarAISummarizer:
    def __init__(self, client: AIClient | None = None):
        self.client = client or AIClient()

    def summarize(self, candidate: RadarCandidate) -> AITaskResult:
        started = time.perf_counter()
        messages = build_summary_prompt(candidate)
        try:
            payload = self.client.complete_json(messages, schema=SUMMARY_SCHEMA)
        except TypeError:
            payload = self.client.complete_json(messages)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return AITaskResult(
            headline=payload.get("headline"),
            short_summary=payload.get("short_summary"),
            why_it_matters=payload.get("why_it_matters"),
            confidence=payload.get("confidence"),
            model_name=self.client.model,
            prompt_version=PROMPT_VERSION,
            processing_time_ms=elapsed_ms,
        )
