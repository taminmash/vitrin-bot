from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re

from radar_engine.pipeline.candidate import RadarCandidate


DEFAULT_ACTIONABILITY_MIN_SCORE = 60
ACTIONABILITY_METADATA_KEY = "actionability_gate"


@dataclass
class ActionabilityResult:
    importance_score: int
    actionability_score: int
    rejection_reason: str | None = None
    matched_signals: list[str] = field(default_factory=list)
    passed: bool = False


PASS_SIGNALS: tuple[tuple[str, int, int, tuple[str, ...]], ...] = (
    ("immigration_change", 85, 90, ("inmigracion", "extranjeria", "residencia", "arraigo", "asilo", "tie", "nie", "visado")),
    ("legal_change", 75, 70, ("ley", "real decreto", "orden ministerial", "reglamento", "entrada en vigor")),
    ("deadline", 80, 85, ("plazo", "fecha limite", "deadline", "solicitud", "convocatoria", "presentacion de solicitudes")),
    ("work_opportunity", 70, 80, ("empleo", "trabajo", "oferta de trabajo", "contrato", "vacante", "job")),
    ("financial_opportunity", 75, 85, ("ayuda", "subvencion", "beca", "bono", "prestacion", "grant", "subsidy")),
    ("tax_change", 80, 80, ("tributaria", "impuesto", "irpf", "iva", "hacienda", "declaracion de la renta")),
    ("healthcare_alert", 90, 90, ("alerta sanitaria", "retirada", "medicamento", "producto sanitario", "recall")),
    ("food_recall", 90, 90, ("alerta alimentaria", "alimento", "lote afectado", "retirada del mercado")),
    ("cybersecurity_warning", 85, 85, ("ciberseguridad", "phishing", "estafa", "incibe", "fraude", "scam")),
    ("public_safety_warning", 85, 85, ("policia", "guardia civil", "seguridad ciudadana", "aviso de seguridad")),
    ("severe_weather", 90, 85, ("aviso rojo", "aviso naranja", "ola de calor", "inundacion", "tormenta", "incendio forestal", "nevada")),
    ("transport_disruption", 80, 85, ("huelga", "corte de trafico", "interrupcion", "cancelacion", "metro", "renfe", "aeropuerto")),
    ("public_event", 60, 65, ("festival", "concierto", "exposicion", "evento gratuito", "actividad familiar")),
    ("government_service_update", 70, 75, ("sede electronica", "cita previa", "tramite", "servicio publico", "certificado digital")),
)

REJECT_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("appointment", ("nombramiento", "nombramientos", "designacion", "designaciones")),
    ("internal_staffing", ("cese", "ceses", "personal directivo", "estructura organica", "cargo")),
    ("promotion", ("ascenso", "promocion interna")),
    ("ceremonial_event", ("ceremonia", "acto institucional", "entrega de premios", "visita institucional")),
    ("institutional_speech", ("discurso", "intervencion del ministro", "comparecencia")),
    ("routine_legal_publication", ("correccion de errores", "publicacion rutinaria", "anuncio formal")),
    ("historical_notice", ("resultado historico", "memoria anual", "balance del ejercicio", "archivo historico")),
    ("duplicate_informational_notice", ("nota informativa duplicada", "duplicado", "recordatorio informativo")),
)


def actionability_min_score() -> int:
    raw_value = os.getenv("RADAR_ACTIONABILITY_MIN_SCORE", str(DEFAULT_ACTIONABILITY_MIN_SCORE))
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_ACTIONABILITY_MIN_SCORE
    return max(0, min(value, 100))


def _normalize_text(value: str) -> str:
    text = value.lower()
    replacements = str.maketrans("áéíóúüñ", "aeiouun")
    return re.sub(r"\s+", " ", text.translate(replacements)).strip()


def _candidate_text(candidate: RadarCandidate) -> str:
    return _normalize_text(
        " ".join(
            str(value or "")
            for value in (
                candidate.title,
                candidate.body,
                candidate.source_category,
                candidate.source_location,
                candidate.source_name,
            )
        )
    )


def _is_expired(candidate: RadarCandidate, now: datetime | None = None) -> bool:
    if not candidate.valid_until:
        return False
    reference = now or datetime.now(candidate.valid_until.tzinfo or timezone.utc)
    valid_until = candidate.valid_until
    if valid_until.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    if valid_until.tzinfo is not None and reference.tzinfo is None:
        reference = reference.replace(tzinfo=valid_until.tzinfo)
    return valid_until < reference


def evaluate_actionability(
    candidate: RadarCandidate,
    min_score: int | None = None,
    now: datetime | None = None,
) -> ActionabilityResult:
    threshold = actionability_min_score() if min_score is None else max(0, min(int(min_score), 100))
    text = _candidate_text(candidate)
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}

    if _is_expired(candidate, now=now):
        return ActionabilityResult(0, 0, "expired_opportunity", [], False)

    # Job connectors normalize this marker before the candidate reaches the
    # shared gate.  Treat it as the existing work-opportunity signal so new
    # connectors do not need source-specific actionability rules.
    if str(metadata.get("content_type") or "").strip().casefold() == "job":
        return ActionabilityResult(70, 80, None, ["work_opportunity"], True)

    for reason, patterns in REJECT_SIGNALS:
        if any(pattern in text for pattern in patterns):
            return ActionabilityResult(10, 10, reason, [], False)

    importance_score = 0
    actionability_score = 0
    matched_signals: list[str] = []
    for signal, importance, actionability, patterns in PASS_SIGNALS:
        if any(pattern in text for pattern in patterns):
            matched_signals.append(signal)
            importance_score = max(importance_score, importance)
            actionability_score = max(actionability_score, actionability)

    source_type = str(candidate.source_type or "").lower()
    if source_type == "official" and matched_signals:
        importance_score = min(100, importance_score + 5)
    if metadata.get("is_urgent") is True:
        importance_score = max(importance_score, 90)
        actionability_score = max(actionability_score, 85)
        matched_signals.append("urgent_metadata")

    if not matched_signals:
        return ActionabilityResult(20, 20, "low_practical_impact", [], False)
    if actionability_score < threshold:
        return ActionabilityResult(
            importance_score,
            actionability_score,
            "below_actionability_threshold",
            matched_signals,
            False,
        )
    return ActionabilityResult(importance_score, actionability_score, None, matched_signals, True)


def apply_actionability_metadata(
    candidate: RadarCandidate,
    result: ActionabilityResult,
    min_score: int | None = None,
) -> RadarCandidate:
    threshold = actionability_min_score() if min_score is None else max(0, min(int(min_score), 100))
    metadata = dict(candidate.metadata or {})
    payload = {
        "importance_score": result.importance_score,
        "actionability_score": result.actionability_score,
        "rejection_reason": result.rejection_reason,
        "passed": result.passed,
        "min_score": threshold,
        "matched_signals": list(result.matched_signals),
    }
    metadata[ACTIONABILITY_METADATA_KEY] = payload
    metadata["importance_score"] = result.importance_score
    metadata["actionability_score"] = result.actionability_score
    metadata["rejection_reason"] = result.rejection_reason
    candidate.metadata = metadata
    return candidate
