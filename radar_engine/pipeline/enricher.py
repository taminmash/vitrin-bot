from __future__ import annotations

from dataclasses import replace

from radar_engine.pipeline.candidate import RadarCandidate


PIPELINE_VERSION = "candidate-v1"


def enrich_candidate(candidate: RadarCandidate) -> RadarCandidate:
    metadata = dict(candidate.metadata or {})
    source_type = (candidate.source_type or "").strip().lower()
    metadata["pipeline_version"] = PIPELINE_VERSION
    metadata["official_source"] = source_type == "official"
    if metadata.get("source_registry_category") == "Government":
        metadata["government_source"] = True
    else:
        metadata["government_source"] = False
    return replace(
        candidate,
        country=(candidate.country or "Spain").strip() or "Spain",
        source_type=source_type,
        trust_level=int(candidate.trust_level),
        metadata=metadata,
    )
