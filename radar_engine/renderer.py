from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from radar_engine.job_presentation import JOB_HELP_TEXT, is_job, job_card


RADAR_HEADER = "🛰️ رادار اسپانیا"
SEPARATOR = "━━━━━━━━━━━━━━━━━━"

TYPE_LABELS = {
    "alert": ("🔥", "فوری"),
    "discount": ("💶", "تخفیف‌ها"),
    "event": ("🎉", "رویداد"),
    "job": ("💼", "کار"),
    "legal": ("🏛", "قوانین"),
    "travel": ("✈️", "سفر"),
    "family": ("👨‍👩‍👧", "خانواده"),
    "weather": ("🌦", "هوا"),
    "transport": ("🚇", "حمل‌ونقل"),
    "economy": ("💰", "اقتصاد"),
    "education": ("📚", "آموزش"),
}

URGENCY_LABELS = {
    "low": "کم",
    "medium": "معمولی",
    "high": "مهم",
    "urgent": "فوری",
}

STATUS_LABELS = {
    "draft": "پیش‌نویس",
    "ready": "آماده انتشار",
    "published": "منتشرشده",
    "expired": "منقضی",
    "failed": "ناموفق",
    "not_sent": "ارسال‌نشده",
}

AUDIENCE_LABELS = {
    "family": "خانواده",
    "shopping": "خرید",
    "discount": "تخفیف",
    "job_seeker": "کارجو",
    "student": "دانشجو",
    "migration": "مهاجرت",
    "residency": "اقامت",
    "digital_nomad": "دیجیتال نومد",
    "autonomo": "خوداشتغال",
    "business": "کسب‌وکار",
    "traveler": "مسافر",
    "all": "همه",
}

NATIONAL_VALUES = {
    "all_spain",
    "national",
    "spain",
    "españa",
    "espana",
    "کل اسپانیا",
    "اسپانیا",
    "همه شهرها",
}


@dataclass(frozen=True)
class ButtonSpec:
    text: str
    callback_data: str | None = None
    url: str | None = None
    switch_inline_query: str | None = None


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def separator() -> str:
    return SEPARATOR


def format_date(value) -> str:
    if not value:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)


def shorten_words(text: str, max_words: int = 36) -> str:
    words = clean_text(text).split()
    if len(words) <= max_words:
        return " ".join(words) if words else "-"
    return " ".join(words[:max_words]).rstrip("،.") + "..."


def _unique(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = clean_text(value)
        key = clean.casefold()
        if clean and key not in seen:
            result.append(clean)
            seen.add(key)
    return result


def type_emoji(item: dict) -> str:
    radar_type = clean_text(item.get("type")) or "alert"
    return TYPE_LABELS.get(radar_type, ("📡", "رادار"))[0]


def type_label(item: dict) -> str:
    radar_type = clean_text(item.get("type"))
    category = clean_text(item.get("category"))
    if radar_type in TYPE_LABELS:
        return TYPE_LABELS[radar_type][1]
    return category or radar_type or "-"


def urgency_label(value) -> str:
    text = clean_text(value)
    return URGENCY_LABELS.get(text, text or "-")


def status_label(value) -> str:
    text = clean_text(value)
    return STATUS_LABELS.get(text, text or "-")


def title_text(item: dict) -> str:
    title = clean_text(item.get("title")) or "-"
    emoji = type_emoji(item)
    if title.startswith(emoji):
        title = title[len(emoji) :].strip()
    return f"{emoji} {title}".strip()


def _is_national(value: str) -> bool:
    return clean_text(value).casefold() in NATIONAL_VALUES


def _localize_place(value: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if _is_national(text):
        return "کل اسپانیا" if text != "Spain" else "اسپانیا"
    return text


def location_text(item: dict) -> str:
    raw_city = clean_text(item.get("city"))
    raw_province = clean_text(item.get("province"))
    raw_country = clean_text(item.get("country"))

    if _is_national(raw_city) or _is_national(raw_province):
        return "کل اسپانیا"
    if not raw_city and not raw_province and (not raw_country or _is_national(raw_country)):
        return "کل اسپانیا"

    values = [_localize_place(raw_city), _localize_place(raw_province)]
    if raw_country:
        values.append("اسپانیا" if _is_national(raw_country) else raw_country)
    localized = _unique(value for value in values if value and value != "کل اسپانیا")
    return "، ".join(localized) or "کل اسپانیا"


def audience_text(item: dict) -> str:
    tags = item.get("audience_tags") or item.get("ai_tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.replace("،", ",").split(",")]
    labels = [AUDIENCE_LABELS.get(clean_text(tag), clean_text(tag)) for tag in tags if clean_text(tag)]
    labels = _unique(labels)
    if not labels or "همه" in labels:
        return "همه فارسی‌زبانان اسپانیا"
    return "، ".join(labels)


def validity_text(item: dict) -> str:
    start = format_date(item.get("start_date"))
    end = format_date(item.get("end_date") or item.get("expires_at"))
    if start == "-" and end == "-":
        return "-"
    return f"{start} تا {end}"


def summary_text(item: dict, *, max_words: int | None = None) -> str:
    text = clean_text(item.get("summary")) or clean_text(item.get("ai_summary"))
    if not text:
        text = clean_text(item.get("body") or item.get("original_text"))
    if max_words:
        return shorten_words(text, max_words)
    return text or "-"


def reason_text(item: dict, *, max_words: int | None = None) -> str:
    text = clean_text(item.get("ai_reason") or item.get("reason"))
    if not text:
        text = clean_text(item.get("summary") or item.get("ai_summary"))
    if max_words:
        return shorten_words(text, max_words)
    return text or "-"


def body_text(item: dict) -> str:
    return clean_text(item.get("body") or item.get("original_text")) or "-"


def source_name(item: dict) -> str:
    return clean_text(item.get("source_name")) or "-"


def source_url(item: dict) -> str:
    return clean_text(item.get("source_url")) or "-"


def section(title: str, body: str) -> list[str]:
    return [title, body or "-"]


def metadata_lines(item: dict, *, include_status: bool = False) -> list[str]:
    lines = [
        f"📍 محدوده: {location_text(item)}",
        f"🏷 دسته: {type_label(item)}",
        f"🎯 مناسب برای: {audience_text(item)}",
        f"⚡ فوریت: {urgency_label(item.get('urgency'))}",
        f"⏳ اعتبار: {validity_text(item)}",
    ]
    if include_status:
        lines.append(f"وضعیت: {status_label(item.get('admin_status') or item.get('content_status') or item.get('channel_status'))}")
    return lines


def _join_blocks(blocks: Iterable[Iterable[str] | str]) -> str:
    lines: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            block_lines = [block]
        else:
            block_lines = list(block)
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(block_lines)
    return "\n".join(lines).strip()


def render_channel_post(item: dict) -> str:
    if is_job(item.get("type") or item.get("category"), item.get("structured_data")):
        return job_card(
            item.get("structured_data"),
            fallback={
                "job_title": item.get("title"),
                "city": item.get("city"),
                "region": item.get("province"),
                "why_it_matters": item.get("ai_reason") or item.get("summary"),
            },
            compact=True,
        )
    return _join_blocks(
        [
            RADAR_HEADER,
            title_text(item),
            SEPARATOR,
            section("📝 خلاصه", summary_text(item, max_words=24)),
            SEPARATOR,
            section("💡 چرا مهم است؟", reason_text(item, max_words=22)),
            SEPARATOR,
            ["🔗 منبع رسمی", source_name(item)],
        ]
    )


def render_details_page(item: dict) -> str:
    if is_job(item.get("type") or item.get("category"), item.get("structured_data")):
        card = job_card(
            item.get("structured_data"),
            fallback={
                "job_title": item.get("title"),
                "city": item.get("city"),
                "region": item.get("province"),
                "why_it_matters": item.get("ai_reason") or item.get("summary"),
                "source_url": item.get("source_url"),
            },
        )
        return _join_blocks([card, SEPARATOR, JOB_HELP_TEXT])
    return _join_blocks(
        [
            RADAR_HEADER,
            title_text(item),
            SEPARATOR,
            section("📝 خلاصه", summary_text(item)),
            SEPARATOR,
            section("💡 چرا مهم است؟", reason_text(item)),
            SEPARATOR,
            section("📄 جزئیات کامل", body_text(item)),
            SEPARATOR,
            metadata_lines(item),
            SEPARATOR,
            ["🔗 منبع رسمی", source_name(item), source_url(item)],
        ]
    )


def render_admin_preview(item: dict) -> str:
    preview = dict(item)
    if item.get("admin_categories"):
        preview["category"] = item.get("admin_categories")
        preview["type"] = ""
    if item.get("admin_audience"):
        preview["audience_tags"] = item.get("admin_audience")
    if item.get("admin_urgency"):
        preview["urgency"] = item.get("admin_urgency")

    if is_job(preview.get("type") or preview.get("category"), preview.get("structured_data")):
        return job_card(
            preview.get("structured_data"),
            fallback={
                "job_title": preview.get("title"),
                "city": preview.get("city"),
                "region": preview.get("province"),
                "why_it_matters": preview.get("ai_reason") or preview.get("summary"),
                "source_url": preview.get("source_url"),
            },
        )

    return _join_blocks(
        [
            RADAR_HEADER,
            title_text(preview),
            SEPARATOR,
            section("📝 خلاصه", summary_text(preview)),
            SEPARATOR,
            section("💡 چرا مهم است؟", reason_text(preview)),
            SEPARATOR,
            section("📄 جزئیات کامل", body_text(preview)),
            SEPARATOR,
            metadata_lines(preview, include_status=True),
            SEPARATOR,
            ["🔗 منبع رسمی", source_name(preview), source_url(preview)],
        ]
    )


def render_ready_preview(item: dict) -> str:
    return render_admin_preview({**item, "admin_status": item.get("admin_status") or "ready"})


def channel_button_specs(
    item: dict,
    deep_link: str,
    reaction_counts: dict | None = None,
    share_url: str | None = None,
) -> list[list[ButtonSpec]]:
    counts = reaction_counts or {}
    item_id = item["id"]
    return [
        [ButtonSpec("📄 مشاهده جزئیات", url=deep_link)],
        [ButtonSpec("📤 اشتراک‌گذاری", url=share_url or deep_link)],
        [
            ButtonSpec(reaction_label("👍 پسندیدم", counts.get("like", 0)), callback_data=f"radar_feedback:like:{item_id}"),
            ButtonSpec(reaction_label("👎 نپسندیدم", counts.get("dislike", 0)), callback_data=f"radar_feedback:dislike:{item_id}"),
        ],
    ]


def details_button_specs(
    item: dict,
    deep_link: str,
    channel_url: str | None = None,
    share_url: str | None = None,
    category: str | None = None,
) -> list[list[ButtonSpec]]:
    category = category or item.get("type") or "all"
    return [
        [ButtonSpec("📤 اشتراک‌گذاری", url=share_url or deep_link)],
        [
            ButtonSpec("⬅️ صفحه قبل", callback_data=f"radar:type:{category}"),
            ButtonSpec("🏠 صفحه اصلی", callback_data="radar:home"),
        ],
    ]


def overview_button_specs(
    item: dict,
    deep_link: str,
    share_url: str | None = None,
    category: str | None = None,
) -> list[list[ButtonSpec]]:
    category = category or item.get("type") or "all"
    return [
        [ButtonSpec("📄 مشاهده جزئیات", callback_data=f"radar:details:{item['id']}")],
        [ButtonSpec("📤 اشتراک‌گذاری", url=share_url or deep_link)],
        [
            ButtonSpec("⬅️ صفحه قبل", callback_data=f"radar:type:{category}"),
            ButtonSpec("🏠 صفحه اصلی", callback_data="radar:home"),
        ],
    ]


def reaction_label(label: str, count) -> str:
    try:
        count_value = int(count or 0)
    except (TypeError, ValueError):
        count_value = 0
    return f"{label} · {count_value}" if count_value else label


def field_log(item: dict) -> dict[str, object]:
    return {
        "id": item.get("id"),
        "has_summary": bool(clean_text(item.get("summary"))),
        "has_ai_summary": bool(clean_text(item.get("ai_summary"))),
        "has_ai_reason": bool(clean_text(item.get("ai_reason"))),
        "has_reason": bool(clean_text(item.get("reason"))),
        "has_body": bool(clean_text(item.get("body"))),
        "has_source_url": bool(clean_text(item.get("source_url"))),
    }
