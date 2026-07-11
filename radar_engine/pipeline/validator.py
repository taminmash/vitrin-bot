from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from radar_engine.pipeline.candidate import RadarCandidate


@dataclass
class ValidationIssue:
    field: str
    code: str
    message: str


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def as_dicts(self) -> list[dict[str, str]]:
        return [issue.__dict__.copy() for issue in self.issues]


def _visible_length(value: str | None) -> int:
    return len((value or "").strip())


def validate_candidate(candidate: RadarCandidate) -> ValidationResult:
    issues: list[ValidationIssue] = []
    if not candidate.title.strip():
        issues.append(ValidationIssue("title", "blank", "Title must not be blank."))
    elif _visible_length(candidate.title) < 5:
        issues.append(ValidationIssue("title", "too_short", "Title is too short."))
    if not candidate.body.strip():
        issues.append(ValidationIssue("body", "blank", "Body must not be blank."))
    elif _visible_length(candidate.body) < 10:
        issues.append(ValidationIssue("body", "too_short", "Body is too short."))
    if not candidate.source_url.strip():
        issues.append(ValidationIssue("source_url", "blank", "Source URL must not be blank."))
    if not candidate.source_key.strip():
        issues.append(ValidationIssue("source_key", "blank", "Source key must not be blank."))
    if not candidate.language.strip():
        issues.append(ValidationIssue("language", "blank", "Language must not be blank."))
    if candidate.valid_from and candidate.valid_until and candidate.valid_until < candidate.valid_from:
        issues.append(ValidationIssue("valid_until", "before_valid_from", "valid_until is before valid_from."))
    if candidate.published_at:
        now = datetime.now(candidate.published_at.tzinfo or timezone.utc)
        if candidate.published_at.year < 1900 or candidate.published_at > now.replace(year=now.year + 2):
            issues.append(ValidationIssue("published_at", "invalid", "published_at is outside a usable range."))
    if not 1 <= int(candidate.trust_level) <= 5:
        issues.append(ValidationIssue("trust_level", "out_of_range", "Trust level must be between 1 and 5."))
    return ValidationResult(is_valid=not issues, issues=issues)
