from __future__ import annotations

from radar_engine.category_headers import category_header
from radar_engine.job_title import UNKNOWN_JOB_TITLE, is_meaningful_job_title


JOB_STRUCTURED_METADATA_KEY = "job_structured"
JOB_HELP_TEXT = (
    "✨ نیاز به کمک برای ارسال درخواست؟\n\n"
    "اگر واجد شرایط این موقعیت شغلی هستید اما برای تهیه رزومه، ارسال درخواست یا انجام مراحل استخدام "
    "نیاز به راهنمایی دارید، تیم ویترین می‌تواند این خدمات را به شما ارائه دهد.\n\n"
    "این خدمت رایگان نیست و مطابق تعرفه خدمات ویترین ارائه می‌شود."
)

FIELD_LABELS = (
    ("job_title", "💼 عنوان شغل"),
    ("employer", "🏢 کارفرما"),
    ("city", "📍 شهر"),
    ("region", "🌍 استان / منطقه"),
    ("salary", "💶 حقوق"),
    ("contract_type", "📄 نوع قرارداد"),
    ("working_hours", "🕒 ساعت کاری"),
    ("publication_date", "📅 تاریخ انتشار"),
    ("deadline", "⏳ مهلت ارسال درخواست"),
    ("requirements", "🎓 پیش‌نیازها"),
    ("language_level", "🗣 سطح زبان"),
    ("job_level", "👔 سطح شغلی"),
    ("experience_required", "📈 سابقه موردنیاز"),
    ("visa_sponsorship", "🛂 Visa Sponsorship"),
    ("relocation_support", "✈️ Relocation Support"),
    ("apply_from_outside_spain", "🌍 امکان اقدام از خارج اسپانیا"),
    ("why_it_matters", "⭐ چرا این فرصت مهم است؟"),
    ("source_url", "🔗 منبع"),
)

DETAIL_FIELD_LABELS = (
    ("full_description", "📝 توضیحات کامل"),
    ("duties", "📋 وظایف"),
    ("education", "🎓 تحصیلات"),
    ("remote_status", "🏠 وضعیت دورکاری"),
    ("source_name", "🏷 نام منبع"),
)


def clean_structured_data(value) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def is_job(category: str | None, structured_data=None) -> bool:
    structured = clean_structured_data(structured_data)
    return (category or "").strip().casefold() == "job" or str(structured.get("category") or "").casefold() == "job"


def radar_score(metadata, classification_confidence, structured_data) -> int | None:
    """Combine available normalized Radar and job signals without another AI call."""
    metadata = clean_structured_data(metadata)
    gate = clean_structured_data(metadata.get("actionability_gate")) or metadata
    data = clean_structured_data(structured_data)
    components: list[float] = []

    for key in ("actionability_score", "importance_score"):
        value = gate.get(key)
        if value is not None:
            try:
                components.append(max(0.0, min(100.0, float(value))))
            except (TypeError, ValueError):
                pass

    try:
        confidence = float(classification_confidence)
        if confidence > 0:
            components.append(max(0.0, min(100.0, confidence * 100)))
    except (TypeError, ValueError):
        pass

    if data:
        sponsorship = str(data.get("visa_sponsorship") or "").strip().upper()
        if sponsorship in {"YES", "NO"}:
            components.append(100.0 if sponsorship == "YES" else 0.0)
        for key in ("salary", "deadline", "language_level"):
            components.append(100.0 if data.get(key) else 0.0)

    if not components:
        return None
    return round(sum(components) / len(components))


def _display_value(key: str, value) -> str | None:
    if value is None:
        return None
    if key == "requirements":
        if not isinstance(value, (list, tuple)):
            return None
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return " • ".join(cleaned) or None
    text = str(value).strip()
    if not text or text.upper() == "UNKNOWN":
        return None
    if key in {"visa_sponsorship", "relocation_support", "apply_from_outside_spain"}:
        return {"YES": "بله", "NO": "خیر"}.get(text.upper())
    return text


def _presented_job_title(data: dict, fallback: dict) -> str:
    for value in (
        data.get("job_title"),
        data.get("normalized_job_title"),
        data.get("occupation"),
        data.get("profession"),
        fallback.get("job_title"),
        fallback.get("title"),
    ):
        if is_meaningful_job_title(value, source_title=True):
            return str(value).strip()
    return UNKNOWN_JOB_TITLE


def job_card(structured_data, *, fallback=None, compact: bool = False) -> str:
    data = clean_structured_data(structured_data)
    fallback = clean_structured_data(fallback)
    merged = {**fallback, **{key: value for key, value in data.items() if value not in (None, "", [])}}
    merged["job_title"] = _presented_job_title(data, fallback)
    keys = (
        "job_title", "employer", "city", "region", "salary", "contract_type",
        "working_hours", "publication_date", "deadline", "requirements", "language_level", "job_level",
        "experience_required", "visa_sponsorship", "relocation_support",
        "apply_from_outside_spain", "why_it_matters", "source_url",
    )
    if compact:
        keys = (
            "job_title", "employer", "city", "salary", "contract_type", "publication_date", "deadline",
            "language_level", "visa_sponsorship", "apply_from_outside_spain",
            "why_it_matters", "source_url",
        )
    labels = dict(FIELD_LABELS)
    blocks = [category_header("job")]
    for key in keys:
        displayed = _display_value(key, merged.get(key))
        if displayed:
            blocks.append(f"{labels[key]}\n{displayed}")
    return "\n\n".join(block for block in blocks if block)


def _concise_requirements(data: dict) -> str:
    raw_requirements = data.get("requirements")
    if isinstance(raw_requirements, (list, tuple)):
        parts = [str(part).strip() for part in raw_requirements if str(part).strip()]
    else:
        text = str(raw_requirements or "").strip()
        parts = [text] if text and text.upper() != "UNKNOWN" else []
    if parts:
        return " • ".join(parts[:2])[:240].rstrip()
    for key in ("language_level", "requirements_or_language", "language_requirement", "required_language"):
        value = _display_value(key, data.get(key))
        if value:
            return value[:240].rstrip()
    return "ذکر نشده"


def job_channel_card(structured_data, *, fallback=None) -> str:
    data = clean_structured_data(structured_data)
    fallback = clean_structured_data(fallback)
    merged = {**fallback, **{key: value for key, value in data.items() if value not in (None, "", [])}}
    title = _presented_job_title(data, fallback)
    city = _display_value("city", merged.get("city")) or "نامشخص"
    contract_type = _display_value("contract_type", merged.get("contract_type")) or "نامشخص"
    requirements = _concise_requirements(merged)
    return "\n\n".join(
        (
            category_header("job"),
            f"💼 عنوان شغل\n{title}",
            f"📍 شهر\n{city}",
            f"📄 نوع قرارداد\n{contract_type}",
            f"🗣 پیش‌نیازها / زبان موردنیاز\n{requirements}",
        )
    )


def job_detail_card(structured_data, *, fallback=None) -> str:
    data = clean_structured_data(structured_data)
    fallback = clean_structured_data(fallback)
    merged = {**fallback, **{key: value for key, value in data.items() if value not in (None, "", [])}}
    if not merged.get("full_description"):
        merged["full_description"] = merged.get("description")
    blocks = [job_card(data, fallback=fallback)]
    for key, label in DETAIL_FIELD_LABELS:
        displayed = _display_value(key, merged.get(key))
        if displayed:
            blocks.append(f"{label}\n{displayed}")
    return "\n\n".join(blocks)
