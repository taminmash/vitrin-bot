from __future__ import annotations

import time

from radar_engine.ai.client import AIClient
from radar_engine.ai.models import AITaskResult
from radar_engine.ai.prompts import PROMPT_VERSION, build_summary_prompt
from radar_engine.job_title import displayed_job_title
from radar_engine.pipeline.candidate import RadarCandidate


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": ["string", "null"]},
        "job_title": {"type": ["string", "null"]},
        "job_title_confidence": {"type": ["number", "null"]},
        "employer": {"type": ["string", "null"]},
        "city": {"type": ["string", "null"]},
        "region": {"type": ["string", "null"]},
        "salary": {"type": ["string", "null"]},
        "contract_type": {"type": ["string", "null"]},
        "working_hours": {"type": ["string", "null"]},
        "deadline": {"type": ["string", "null"]},
        "requirements": {"type": ["array", "null"], "items": {"type": "string"}},
        "language_level": {"type": ["string", "null"]},
        "job_level": {"type": ["string", "null"]},
        "experience_required": {"type": ["string", "null"]},
        "visa_sponsorship": {"type": ["string", "null"], "enum": ["YES", "NO", "UNKNOWN", None]},
        "relocation_support": {"type": ["string", "null"], "enum": ["YES", "NO", "UNKNOWN", None]},
        "apply_from_outside_spain": {"type": ["string", "null"], "enum": ["YES", "NO", "UNKNOWN", None]},
        "why_it_matters": {"type": ["string", "null"]},
        "full_text_fa": {"type": ["string", "null"]},
        "source_url": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
    },
    "required": [
        "category", "job_title", "job_title_confidence", "employer", "city", "region", "salary", "contract_type",
        "working_hours", "deadline", "requirements", "language_level", "job_level",
        "experience_required", "visa_sponsorship", "relocation_support",
        "apply_from_outside_spain", "full_text_fa", "source_url", "confidence",
    ],
}

STRUCTURED_KEYS = tuple(key for key in SUMMARY_SCHEMA["properties"] if key != "confidence")


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
        structured = {key: payload.get(key) for key in STRUCTURED_KEYS}
        for key in ("visa_sponsorship", "relocation_support", "apply_from_outside_spain"):
            value = str(structured.get(key) or "UNKNOWN").strip().upper()
            structured[key] = value if value in {"YES", "NO", "UNKNOWN"} else "UNKNOWN"
        structured["source_url"] = structured.get("source_url") or candidate.source_url
        if structured.get("category"):
            structured["category"] = str(structured["category"]).strip().casefold()
        is_job_candidate = (
            structured.get("category") == "job"
            or str(candidate.source_category or "").strip().casefold() in {"job", "jobs"}
            or str(candidate.metadata.get("content_type") or "").strip().casefold() == "job"
        )
        if is_job_candidate:
            job_title = displayed_job_title(
                candidate.title,
                candidate.metadata,
                structured.get("job_title"),
                structured.get("job_title_confidence"),
            )
            structured["job_title"] = job_title
        else:
            job_title = (structured.get("job_title") or candidate.title or "").strip()
        summary_parts = [
            structured.get("employer"), structured.get("city"), structured.get("salary"),
            structured.get("contract_type"), structured.get("deadline"),
        ]
        short_summary = " | ".join(str(value).strip() for value in summary_parts if value)
        if not short_summary:
            short_summary = job_title
        return AITaskResult(
            headline=job_title,
            short_summary=short_summary,
            why_it_matters=payload.get("why_it_matters") or "",
            confidence=payload.get("confidence"),
            model_name=self.client.model,
            prompt_version=PROMPT_VERSION,
            processing_time_ms=elapsed_ms,
            structured_data=structured,
        )
