from __future__ import annotations

from radar_engine.category_headers import category_header


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
    ("deadline", "📅 مهلت درخواست"),
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


def clean_structured_data(value) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def is_job(category: str | None, structured_data=None) -> bool:
    structured = clean_structured_data(structured_data)
    return (category or "").strip().casefold() == "job" or str(structured.get("category") or "").casefold() == "job"


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


def job_card(structured_data, *, fallback=None, compact: bool = False) -> str:
    data = clean_structured_data(structured_data)
    fallback = clean_structured_data(fallback)
    merged = {**fallback, **{key: value for key, value in data.items() if value not in (None, "", [])}}
    keys = (
        "job_title", "employer", "city", "region", "salary", "contract_type",
        "working_hours", "deadline", "requirements", "language_level", "job_level",
        "experience_required", "visa_sponsorship", "relocation_support",
        "apply_from_outside_spain", "why_it_matters", "source_url",
    )
    if compact:
        keys = (
            "job_title", "employer", "city", "salary", "contract_type", "deadline",
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
