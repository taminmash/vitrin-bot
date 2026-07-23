from __future__ import annotations

from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.job_title import existing_job_title


PROMPT_VERSION = "radar-structured-v5"


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
- Set visa_sponsorship to YES only when the original source explicitly confirms employer-provided visa sponsorship or explicit support for the required work visa/permit.
- Relocation, English-friendly work, an international company, suitability for foreigners, applying from abroad, or probable/possible support are not visa sponsorship.
- Set visa_sponsorship to NO only when the source explicitly refuses sponsorship; otherwise use UNKNOWN.
- When visa_sponsorship is YES, visa_sponsorship_evidence must be one short verbatim excerpt copied from the original title or body.
- Never translate, paraphrase, clean up, or invent visa_sponsorship_evidence.
- For visa_sponsorship NO or UNKNOWN, return null for visa_sponsorship_evidence.
- For job_title, extract the actual profession from the source; never invent one.
- job_title must be Persian, contain at most 6 words, and contain no punctuation or explanation.
- Never return generic job_title phrases such as فرصت شغلی, موقعیت شغلی, استخدام, or فرصت استخدام.
- If the profession is not explicitly identifiable (for example only "una plaza" or "puesto"), return job_title as "UNKNOWN".
- job_title_confidence must measure confidence in the extracted profession from 0 to 1.
- Return structured JSON only.
"""


def build_summary_prompt(candidate: RadarCandidate) -> list[dict[str, str]]:
    title_extraction_needed = "NO" if existing_job_title(candidate.title, candidate.metadata) else "YES"
    full_translation_needed = "YES" if candidate.source_key.strip().casefold() == "boe" else "NO"
    user_prompt = f"""Extract a structured Persian record for this Radar candidate.

job_title_extraction_needed: {title_extraction_needed}
If job_title_extraction_needed is NO, return null for job_title and job_title_confidence.
full_persian_translation_needed: {full_translation_needed}
If full_persian_translation_needed is YES, translate the complete source body into factual Persian as full_text_fa.
Preserve all facts and paragraph order; do not summarize, omit, interpret, or add information.
If full_persian_translation_needed is NO, return null for full_text_fa.

Return JSON with exactly these keys:
- category
- job_title
- job_title_confidence
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
- visa_sponsorship_evidence
- relocation_support
- apply_from_outside_spain
- why_it_matters
- full_text_fa
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
