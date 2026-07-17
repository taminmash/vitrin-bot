from __future__ import annotations

from radar_engine.pipeline.actionability import ACTIONABILITY_METADATA_KEY
from radar_engine.job_presentation import is_job, job_card, radar_score


SAFE_TELEGRAM_TEXT_LIMIT = 3800
TRUNCATION_MARKER = "… [متن اصلی کوتاه شده است]"
AI_TRUNCATION_MARKER = "… [متن هوش مصنوعی کوتاه شده است]"
LIST_TRUNCATION_MARKER = "… [فهرست کوتاه شده است]"
SOURCE_NAME_TRUNCATION_MARKER = "… [نام منبع کوتاه شده است]"
URL_TRUNCATION_MARKER = "…[نشانی کوتاه شده است]…"
QUEUE_MORE_ITEMS_NOTE = "موارد بیشتری باقی مانده است."
SHORT_TRUNCATION_MARKER = "…"


def truncate_text(value, max_length: int, marker: str = TRUNCATION_MARKER) -> str:
    text = (value or "").strip()
    if max_length <= 0:
        return marker[: max(0, max_length)]
    if len(text) <= max_length:
        return text
    if max_length <= len(marker):
        return marker[:max_length]
    return text[: max_length - len(marker)].rstrip() + marker


def truncate_middle(value, max_length: int, marker: str = URL_TRUNCATION_MARKER) -> str:
    text = (value or "").strip()
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    if max_length <= len(marker):
        return marker[:max_length]
    remaining = max_length - len(marker)
    left = max(1, remaining // 2)
    right = max(1, remaining - left)
    return f"{text[:left]}{marker}{text[-right:]}"


def _format_list(values, labeler=None) -> str:
    values = values or []
    if labeler:
        labels = labeler(values)
    else:
        labels = values
    return "، ".join(labels) or "-"


def _actionability_scores(candidate) -> tuple[str, str]:
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    gate = metadata.get(ACTIONABILITY_METADATA_KEY)
    if not isinstance(gate, dict):
        gate = metadata
    importance = gate.get("importance_score")
    actionability = gate.get("actionability_score")
    return (
        str(importance) if importance is not None else "Unknown",
        str(actionability) if actionability is not None else "Unknown",
    )


def _review_item_text_from_fields(fields: dict[str, str], classification) -> str:
    return (
        "🧭 بازبینی رادار\n\n"
        "متن اصلی:\n"
        f"{fields['title']}\n"
        f"{fields['body']}\n\n"
        "خلاصه هوش مصنوعی:\n"
        f"{fields['headline']}\n"
        f"{fields['summary']}\n"
        f"چرا مهم است: {fields['why_it_matters']}\n"
        "\n"
        "Radar V2:\n"
        f"Importance: {fields['importance_score']}\n"
        f"Actionability: {fields['actionability_score']}\n\n"
        "طبقه‌بندی هوش مصنوعی:\n"
        f"دسته اصلی: {fields['categories']}\n"
        f"تگ‌های دسته: {fields['category_tags']}\n"
        f"مخاطب: {fields['audience']}\n"
        f"محدوده: {fields['geographic_scope']}\n"
        f"شهرها: {fields['cities']}\n"
        f"فوریت: {fields['urgency']}\n"
        f"اولویت: {classification.priority_score}\n"
        "\n"
        "منبع اصلی:\n"
        f"{fields['source_name']}\n"
        f"{fields['source_url']}"
    )


def _reduce_field(fields: dict[str, str], key: str, marker: str, max_chars: int = 0) -> bool:
    current = fields[key]
    if len(current) <= max_chars:
        return False
    if max_chars <= 0:
        max_chars = len(marker)
    fields[key] = truncate_text(current, max_chars, marker=marker)
    return True


def _guarantee_review_item_length(fields: dict[str, str], classification, max_length: int) -> str:
    if max_length <= 0:
        return ""

    text = _review_item_text_from_fields(fields, classification)
    if len(text) <= max_length:
        return text

    reduction_order = (
        ("body", TRUNCATION_MARKER, 0),
        ("title", SHORT_TRUNCATION_MARKER, 0),
        ("why_it_matters", AI_TRUNCATION_MARKER, 0),
        ("summary", AI_TRUNCATION_MARKER, 0),
        ("headline", AI_TRUNCATION_MARKER, 0),
        ("category_tags", LIST_TRUNCATION_MARKER, 0),
        ("audience", LIST_TRUNCATION_MARKER, 0),
        ("cities", LIST_TRUNCATION_MARKER, 0),
        ("categories", LIST_TRUNCATION_MARKER, len(str(classification.primary_category))),
        ("source_name", SOURCE_NAME_TRUNCATION_MARKER, 0),
    )

    for key, marker, minimum in reduction_order:
        text = _review_item_text_from_fields(fields, classification)
        if len(text) <= max_length:
            return text
        overage = len(text) - max_length
        current_length = len(fields[key])
        target_length = max(minimum, current_length - overage)
        if target_length >= current_length:
            target_length = minimum
        _reduce_field(fields, key, marker, target_length)

    text = _review_item_text_from_fields(fields, classification)
    if len(text) <= max_length:
        return text

    fixed_without_url = len(text) - len(fields["source_url"])
    url_budget = max(0, max_length - fixed_without_url)
    fields["source_url"] = truncate_middle(fields["source_url"], url_budget)
    text = _review_item_text_from_fields(fields, classification)
    if len(text) <= max_length:
        return text

    # Tiny test limits may be smaller than the required labels themselves.
    return text[:max_length]


def build_review_item_text(
    item,
    category_labeler=None,
    audience_labeler=None,
    urgency_labeler=None,
    max_length: int = SAFE_TELEGRAM_TEXT_LIMIT,
) -> str:
    candidate = item.candidate
    summary = item.summary
    classification = item.classification
    if is_job(classification.primary_category, summary.structured_data):
        fallback = {
            "job_title": summary.headline or candidate.title,
            "city": (classification.cities or [None])[0],
            "why_it_matters": summary.why_it_matters,
            "source_url": candidate.source_url,
        }
        score = radar_score(candidate.metadata, classification.confidence, summary.structured_data)
        score_block = f"⭐ امتیاز Radar\n{score} / 100\n\n" if score is not None else ""
        return truncate_text(
            score_block + job_card(summary.structured_data, fallback=fallback),
            max_length,
            marker=SHORT_TRUNCATION_MARKER,
        )
    categories = _format_list([classification.primary_category], category_labeler) or classification.primary_category
    category_tags = _format_list(classification.category_tags, category_labeler)
    audience = _format_list(classification.audience_tags, audience_labeler)
    cities = _format_list(classification.cities)
    urgency = urgency_labeler(classification.urgency) if urgency_labeler else classification.urgency
    importance_score, actionability_score = _actionability_scores(candidate)
    fields = {
        "title": candidate.title or "-",
        "body": candidate.body or "-",
        "headline": summary.headline,
        "summary": summary.summary,
        "why_it_matters": summary.why_it_matters,
        "importance_score": importance_score,
        "actionability_score": actionability_score,
        "categories": categories,
        "category_tags": category_tags,
        "audience": audience,
        "geographic_scope": classification.geographic_scope,
        "cities": cities,
        "urgency": urgency,
        "source_name": candidate.source_name,
        "source_url": candidate.source_url,
    }
    return _guarantee_review_item_length(fields, classification, max_length)


def build_review_queue_display(items, report, max_length: int = SAFE_TELEGRAM_TEXT_LIMIT):
    lines = [
        "🧭 بازبینی رادار",
        "",
        f"در انتظار: {report.pending}",
        f"تأیید شده: {report.approved}",
        f"رد شده: {report.rejected}",
        f"نیازمند ویرایش: {report.needs_edit}",
        "",
    ]
    if not items:
        lines.append("موردی برای بازبینی وجود ندارد.")
        return truncate_text("\n".join(lines).strip(), max_length, marker=SHORT_TRUNCATION_MARKER), []

    lines.append("موارد آماده بازبینی:")
    visible_items = []
    hidden_count = 0
    for index, item in enumerate(items):
        candidate = item.candidate
        classification = item.classification
        title = truncate_text(candidate.title or "-", 90, marker=SHORT_TRUNCATION_MARKER)
        row = (
            f"- {title} | {classification.primary_category} | "
            f"{classification.urgency} | priority {classification.priority_score}"
        )
        candidate_lines = lines + [row]
        remaining = len(items) - index - 1
        if remaining:
            candidate_lines.append(QUEUE_MORE_ITEMS_NOTE)
        candidate_text = "\n".join(candidate_lines).strip()
        if len(candidate_text) > max_length:
            hidden_count = len(items) - index
            break
        lines.append(row)
        visible_items.append(item)

    if hidden_count or len(visible_items) < len(items):
        if not lines[-1].endswith(QUEUE_MORE_ITEMS_NOTE):
            note_text = "\n".join(lines + [QUEUE_MORE_ITEMS_NOTE]).strip()
            if len(note_text) <= max_length:
                lines.append(QUEUE_MORE_ITEMS_NOTE)
    text = "\n".join(lines).strip()
    if len(text) <= max_length:
        return text, visible_items
    return truncate_text(text, max_length, marker=SHORT_TRUNCATION_MARKER), visible_items
