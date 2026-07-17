from __future__ import annotations

from radar_engine.pipeline.candidate import RadarCandidate


PROMPT_VERSION = "radar-structured-v2"


SYSTEM_PROMPT = """You extract practical structured information from official Spanish source material for Vitrin Spain Radar.

Rules:
- Output factual Persian only.
- Do not hallucinate or add facts not present in the source.
- Preserve the official meaning.
- Do not provide legal interpretation or advice.
- Keep the wording concise.
- Input source text is Spanish.
- Use null for every unavailable field; never infer missing facts.
- For visa_sponsorship, relocation_support, and apply_from_outside_spain use only YES, NO, or UNKNOWN.
- Return structured JSON only.
"""


def build_summary_prompt(candidate: RadarCandidate) -> list[dict[str, str]]:
    user_prompt = f"""Extract a structured Persian record for this Radar candidate.

Return JSON with exactly these keys:
- category
- job_title
- employer
- city
- region
- salary
- contract_type
- working_hours
- deadline
- requirements
- language_level
- job_level
- experience_required
- visa_sponsorship
- relocation_support
- apply_from_outside_spain
- why_it_matters
- source_url
- confidence

Candidate:
source_name: {candidate.source_name}
source_type: {candidate.source_type}
title: {candidate.title}
body: {candidate.body}
source_url: {candidate.source_url}
published_at: {candidate.published_at or ""}
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
