from __future__ import annotations

import time

from radar_engine.ai.client import AIClient
from radar_engine.classification.models import ClassificationSource, RadarClassificationResult
from radar_engine.classification.prompts import PROMPT_VERSION, build_classification_prompt
from radar_engine.taxonomy import (
    RADAR_AUDIENCE_VALUES,
    RADAR_CATEGORY_VALUES,
    RADAR_CITY_VALUES,
    RADAR_GEOGRAPHIC_SCOPE_VALUES,
    RADAR_URGENCY_VALUES,
)


CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_category": {"type": "string", "enum": list(RADAR_CATEGORY_VALUES)},
        "category_tags": {"type": "array", "items": {"type": "string", "enum": list(RADAR_CATEGORY_VALUES)}},
        "audience_tags": {"type": "array", "items": {"type": "string", "enum": list(RADAR_AUDIENCE_VALUES)}},
        "cities": {"type": "array", "items": {"type": "string", "enum": list(RADAR_CITY_VALUES)}},
        "geographic_scope": {"type": "string", "enum": list(RADAR_GEOGRAPHIC_SCOPE_VALUES)},
        "urgency": {"type": "string", "enum": list(RADAR_URGENCY_VALUES)},
        "priority_score": {"type": "integer"},
        "confidence": {"type": "number"},
    },
    "required": [
        "primary_category",
        "category_tags",
        "audience_tags",
        "cities",
        "geographic_scope",
        "urgency",
        "priority_score",
        "confidence",
    ],
}


class RadarAIClassifier:
    def __init__(self, client: AIClient | None = None):
        self.client = client or AIClient()

    def classify(self, source: ClassificationSource) -> RadarClassificationResult:
        started = time.perf_counter()
        messages = build_classification_prompt(source)
        try:
            payload = self.client.complete_json(messages, schema=CLASSIFICATION_SCHEMA)
        except TypeError:
            payload = self.client.complete_json(messages)
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
