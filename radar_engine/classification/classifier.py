from __future__ import annotations

import time

from radar_engine.ai.client import OpenAIClient
from radar_engine.classification.models import ClassificationSource, RadarClassificationResult
from radar_engine.classification.prompts import PROMPT_VERSION, build_classification_prompt


class RadarAIClassifier:
    def __init__(self, client: OpenAIClient | None = None):
        self.client = client or OpenAIClient()

    def classify(self, source: ClassificationSource) -> RadarClassificationResult:
        started = time.perf_counter()
        payload = self.client.complete_json(build_classification_prompt(source))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RadarClassificationResult(
            candidate_id=source.candidate_id,
            primary_category=payload.get("primary_category"),
            category_tags=payload.get("category_tags"),
            audience_tags=payload.get("audience_tags"),
            cities=payload.get("cities"),
            geographic_scope=payload.get("geographic_scope"),
            urgency=payload.get("urgency"),
            priority_score=payload.get("priority_score"),
            confidence=payload.get("confidence"),
            model_name=self.client.model,
            prompt_version=PROMPT_VERSION,
            processing_time_ms=elapsed_ms,
        )
