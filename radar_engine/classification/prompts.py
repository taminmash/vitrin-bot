from __future__ import annotations

import json

from radar_engine.classification.models import ClassificationSource
from radar_engine.taxonomy import (
    RADAR_AUDIENCE_VALUES,
    RADAR_CATEGORY_VALUES,
    RADAR_CITY_VALUES,
    RADAR_GEOGRAPHIC_SCOPE_VALUES,
    RADAR_URGENCY_VALUES,
)


PROMPT_VERSION = "radar-classification-v1"

SYSTEM_PROMPT = """You classify Vitrin Spain Radar candidates.
Return structured JSON only.
Use only the allowed controlled vocabularies.
Do not invent facts.
Do not reinterpret laws or provide legal advice.
Do not infer a city without evidence.
Use national scope when the content clearly applies across Spain.
Use empty audience and city lists when evidence is insufficient.
Select exactly one primary_category.
category_tags may contain only allowed category values.
urgency must reflect time sensitivity, not sensationalism.
priority_score must reflect usefulness to Persian-speaking residents in Spain.
confidence must reflect classification certainty."""


def _json_list(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def build_classification_prompt(source: ClassificationSource) -> list[dict[str, str]]:
    candidate = source.candidate
    user_prompt = f"""Classify this Radar candidate.

Prompt version: {PROMPT_VERSION}

Original Spanish candidate:
title: {candidate.title}
body: {candidate.body}
language: {candidate.language}
source_name: {candidate.source_name}
source_url: {candidate.source_url}
canonical_url: {candidate.canonical_url or ""}
source_category: {candidate.source_category or ""}
source_location: {candidate.source_location or ""}
source_type: {candidate.source_type}
published_at: {candidate.published_at or ""}
valid_from: {candidate.valid_from or ""}
valid_until: {candidate.valid_until or ""}
country: {candidate.country}

Persian summarization result:
headline: {source.ai_headline}
summary: {source.ai_summary}
why_it_matters: {source.ai_why_it_matters}

Allowed primary_category and category_tags values:
{_json_list(RADAR_CATEGORY_VALUES)}

Allowed audience_tags values:
{_json_list(RADAR_AUDIENCE_VALUES)}

Allowed cities values:
{_json_list(RADAR_CITY_VALUES)}

Allowed geographic_scope values:
{_json_list(RADAR_GEOGRAPHIC_SCOPE_VALUES)}

Allowed urgency values:
{_json_list(RADAR_URGENCY_VALUES)}

Return a JSON object with exactly these keys:
primary_category: string
category_tags: array of strings
audience_tags: array of strings
cities: array of strings
geographic_scope: string
urgency: string
priority_score: integer from 0 to 100
confidence: number from 0.0 to 1.0

Do not include headline, summary, why_it_matters, translation, publication text,
legal advice, recommendations, publish decision, or Telegram content."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
