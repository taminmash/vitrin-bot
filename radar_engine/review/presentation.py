from __future__ import annotations


SAFE_TELEGRAM_TEXT_LIMIT = 3800
TRUNCATION_MARKER = "… [متن اصلی کوتاه شده است]"
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


def _format_list(values, labeler=None) -> str:
    values = values or []
    if labeler:
        labels = labeler(values)
    else:
        labels = values
    return "، ".join(labels) or "-"


def _build_original_block(header: str, title: str, body: str, available_length: int) -> str:
    if available_length <= 0:
        return ""

    title = title or "-"
    body = body or "-"
    minimum_title_length = min(len(title), 120)
    title_budget = min(len(title), max(1, min(180, available_length - len(header) - 1)))
    if available_length - len(header) - title_budget - 1 > 0:
        title_text = truncate_text(title, title_budget, marker=SHORT_TRUNCATION_MARKER)
    else:
        title_text = truncate_text(title, max(1, available_length - len(header) - 1), marker=SHORT_TRUNCATION_MARKER)

    prefix = f"{header}{title_text}\n"
    body_budget = available_length - len(prefix)
    if body_budget <= 0 and len(title_text) > minimum_title_length:
        title_text = truncate_text(title, minimum_title_length, marker=SHORT_TRUNCATION_MARKER)
        prefix = f"{header}{title_text}\n"
        body_budget = available_length - len(prefix)

    body_text = truncate_text(body, body_budget)
    return f"{prefix}{body_text}"


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
    categories = _format_list([classification.primary_category], category_labeler) or classification.primary_category
    category_tags = _format_list(classification.category_tags, category_labeler)
    audience = _format_list(classification.audience_tags, audience_labeler)
    cities = _format_list(classification.cities)
    urgency = urgency_labeler(classification.urgency) if urgency_labeler else classification.urgency

    source_section = (
        "منبع اصلی:\n"
        f"{candidate.source_name}\n"
        f"{candidate.source_url}"
    )
    preserved_tail = (
        "\n\nخلاصه هوش مصنوعی:\n"
        f"{summary.headline}\n"
        f"{summary.summary}\n"
        f"چرا مهم است: {summary.why_it_matters}\n"
        f"اعتماد خلاصه: {summary.confidence}\n\n"
        "طبقه‌بندی هوش مصنوعی:\n"
        f"دسته اصلی: {categories}\n"
        f"تگ‌های دسته: {category_tags}\n"
        f"مخاطب: {audience}\n"
        f"محدوده: {classification.geographic_scope}\n"
        f"شهرها: {cities}\n"
        f"فوریت: {urgency}\n"
        f"اولویت: {classification.priority_score}\n"
        f"اعتماد طبقه‌بندی: {classification.confidence}\n\n"
        f"{source_section}"
    )
    header = "🧭 بازبینی رادار\n\nمتن اصلی:\n"
    title = candidate.title or "-"
    body = candidate.body or "-"
    available_for_original = max_length - len(preserved_tail)
    original_block = _build_original_block(header, title, body, available_for_original)
    text = f"{original_block}{preserved_tail}"
    if len(text) <= max_length:
        return text

    # Preserve AI review details and source URL; only the original source block may shrink.
    original_block = _build_original_block(header, title, body, max(0, max_length - len(preserved_tail)))
    return f"{original_block}{preserved_tail}"


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
        return "\n".join(lines).strip(), []

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
    return "\n".join(lines).strip(), visible_items
