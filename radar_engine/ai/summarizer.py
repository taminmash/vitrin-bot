from __future__ import annotations

import time

from radar_engine.ai.client import OpenAIClient
from radar_engine.ai.models import AITaskResult
from radar_engine.ai.prompts import PROMPT_VERSION, build_summary_prompt
from radar_engine.pipeline.candidate import RadarCandidate


class RadarAISummarizer:
    def __init__(self, client: OpenAIClient | None = None):
        self.client = client or OpenAIClient()

    def summarize(self, candidate: RadarCandidate) -> AITaskResult:
        started = time.perf_counter()
        payload = self.client.complete_json(build_summary_prompt(candidate))
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
