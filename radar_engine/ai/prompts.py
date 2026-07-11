from __future__ import annotations

from radar_engine.pipeline.candidate import RadarCandidate


PROMPT_VERSION = "radar-summary-v1"


SYSTEM_PROMPT = """You summarize official Spanish source material for Vitrin Spain Radar.

Rules:
- Output factual Persian only.
- Do not hallucinate or add facts not present in the source.
- Preserve the official meaning.
- Do not provide legal interpretation or advice.
- Keep the wording concise.
- Input source text is Spanish.
- Return structured JSON only.
"""


def build_summary_prompt(candidate: RadarCandidate) -> list[dict[str, str]]:
    user_prompt = f"""Create a concise Persian summary for this Radar candidate.

Return JSON with exactly these keys:
- headline
- short_summary
- why_it_matters
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
