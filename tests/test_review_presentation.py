import unittest

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.review.models import RadarReviewQueueItem, RadarSummaryForReview, ReviewQueueReport
from radar_engine.review.presentation import (
    AI_TRUNCATION_MARKER,
    LIST_TRUNCATION_MARKER,
    QUEUE_MORE_ITEMS_NOTE,
    SAFE_TELEGRAM_TEXT_LIMIT,
    TRUNCATION_MARKER,
    URL_TRUNCATION_MARKER,
    build_review_item_text,
    build_review_queue_display,
)


def make_candidate(**overrides):
    data = {
        "raw_item_id": "raw-1",
        "source_key": "boe",
        "source_name": "BOE",
        "external_id": "external-1",
        "title": "اعلامیه رسمی درباره Málaga",
        "body": "متن رسمی کوتاه برای بازبینی.",
        "language": "es",
        "source_url": "https://www.boe.es/test/unicode",
        "canonical_url": "https://www.boe.es/test/unicode",
        "published_at": None,
        "valid_from": None,
        "valid_until": None,
        "source_category": "Government",
        "source_location": "Spain",
        "source_type": "official",
        "trust_level": 5,
        "country": "Spain",
        "candidate_status": "pending_ai",
        "metadata": {
            "actionability_gate": {
                "importance_score": 85,
                "actionability_score": 90,
                "rejection_reason": None,
                "passed": True,
            }
        },
    }
    data.update(overrides)
    return RadarCandidate(**data)


def make_summary(**overrides):
    data = {
        "ai_result_id": "ai-1",
        "headline": "تیتر هوش مصنوعی",
        "summary": "خلاصه کوتاه هوش مصنوعی برای ادمین.",
        "why_it_matters": "این مورد برای فارسی زبان ها مهم است.",
        "confidence": 0.82,
    }
    data.update(overrides)
    return RadarSummaryForReview(**data)


def make_classification(**overrides):
    data = {
        "candidate_id": "candidate-1",
        "primary_category": "legal",
        "category_tags": ["legal"],
        "audience_tags": ["migration"],
        "cities": [],
        "geographic_scope": "national",
        "urgency": "high",
        "priority_score": 80,
        "confidence": 0.9,
        "model_name": "model",
        "prompt_version": "radar-classification-v1",
        "processing_time_ms": 12,
    }
    data.update(overrides)
    return RadarClassificationResult(**data)


def make_item(**overrides):
    candidate = overrides.pop("candidate", make_candidate())
    summary = overrides.pop("summary", make_summary())
    classification = overrides.pop("classification", make_classification())
    return RadarReviewQueueItem(
        candidate_id=overrides.pop("candidate_id", classification.candidate_id),
        candidate=candidate,
        summary=summary,
        classification=classification,
    )


class ReviewPresentationTests(unittest.TestCase):
    def test_long_boe_body_is_truncated_without_losing_review_context(self):
        source_url = "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-12345"
        item = make_item(
            candidate=make_candidate(
                body=("Texto oficial del BOE sobre residencia y administracion. " * 300),
                source_url=source_url,
                canonical_url=source_url,
            )
        )

        text = build_review_item_text(item)

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertIn(TRUNCATION_MARKER, text)
        self.assertIn(source_url, text)
        self.assertIn("تیتر هوش مصنوعی", text)
        self.assertIn("خلاصه کوتاه هوش مصنوعی", text)
        self.assertIn("این مورد برای فارسی زبان ها مهم است", text)
        self.assertIn("legal", text)
        self.assertIn("national", text)
        self.assertIn("high", text)

    def test_short_review_item_content_remains_unchanged(self):
        body = "متن رسمی کوتاه برای بازبینی در Málaga."
        item = make_item(candidate=make_candidate(body=body))

        text = build_review_item_text(item)

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertNotIn(TRUNCATION_MARKER, text)
        self.assertIn(body, text)
        self.assertIn("Málaga", text)

    def test_review_item_shows_actionability_scores(self):
        item = make_item()

        text = build_review_item_text(item)

        self.assertIn("Importance: 85", text)
        self.assertIn("Actionability: 90", text)

    def test_queue_truncates_long_titles_and_keeps_message_safe(self):
        items = [
            make_item(
                candidate_id=f"candidate-{index}",
                candidate=make_candidate(
                    raw_item_id=f"raw-{index}",
                    title=f"عنوان بسیار طولانی درباره Málaga و خدمات اداری {index} " * 20,
                ),
                classification=make_classification(candidate_id=f"candidate-{index}"),
            )
            for index in range(80)
        ]

        text, visible_items = build_review_queue_display(
            items,
            ReviewQueueReport(pending=80, approved=1, rejected=2, needs_edit=3),
        )

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertGreater(len(visible_items), 0)
        self.assertLess(len(visible_items), len(items))
        self.assertIn(QUEUE_MORE_ITEMS_NOTE, text)
        self.assertIn("…", text)
        self.assertIn("Málaga", text)

    def test_queue_short_content_lists_all_items(self):
        items = [
            make_item(
                candidate_id=f"candidate-{index}",
                candidate=make_candidate(raw_item_id=f"raw-{index}", title=f"عنوان {index}"),
                classification=make_classification(candidate_id=f"candidate-{index}"),
            )
            for index in range(3)
        ]

        text, visible_items = build_review_queue_display(items, ReviewQueueReport(pending=3))

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertEqual([item.candidate_id for item in visible_items], [item.candidate_id for item in items])
        self.assertNotIn(QUEUE_MORE_ITEMS_NOTE, text)
        self.assertIn("عنوان 0", text)
        self.assertIn("عنوان 1", text)
        self.assertIn("عنوان 2", text)

    def test_extremely_long_ai_fields_are_truncated_after_original_text(self):
        item = make_item(
            candidate=make_candidate(body="متن اصلی کوتاه."),
            summary=make_summary(
                headline="تیتر بلند " * 500,
                summary="خلاصه بلند " * 500,
                why_it_matters="دلیل بلند " * 500,
            ),
        )

        text = build_review_item_text(item)

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertIn(AI_TRUNCATION_MARKER, text)
        self.assertIn("خلاصه هوش مصنوعی:", text)
        self.assertIn("طبقه‌بندی هوش مصنوعی:", text)
        self.assertIn("دسته اصلی:", text)
        self.assertIn("فوریت:", text)
        self.assertIn("اولویت:", text)
        self.assertIn("اعتماد طبقه‌بندی:", text)
        self.assertIn("https://www.boe.es/test/unicode", text)

    def test_extremely_long_source_name_is_shortened_before_url(self):
        source_url = "https://www.boe.es/test/source-name"
        item = make_item(
            candidate=make_candidate(
                source_name="BOE source name " * 500,
                source_url=source_url,
                canonical_url=source_url,
            )
        )

        text = build_review_item_text(item)

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertIn("نام منبع کوتاه شده است", text)
        self.assertIn(source_url, text)

    def test_extremely_long_url_uses_middle_truncation(self):
        source_url = "https://www.boe.es/" + ("very-long-path/" * 500) + "final-document"
        item = make_item(candidate=make_candidate(source_url=source_url, canonical_url=source_url))

        text = build_review_item_text(item)

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertIn(URL_TRUNCATION_MARKER, text)
        self.assertIn("https://www.boe.es/", text)
        self.assertIn("final-document", text)

    def test_all_fields_long_still_respects_limit_and_keeps_essentials_when_practical(self):
        source_url = "https://www.boe.es/" + ("path/" * 300) + "end"
        item = make_item(
            candidate=make_candidate(
                title="عنوان اصلی بسیار بلند " * 300,
                body="بدنه اصلی بسیار بلند " * 600,
                source_name="BOE official source " * 300,
                source_url=source_url,
                canonical_url=source_url,
            ),
            summary=make_summary(
                headline="تیتر هوش مصنوعی بسیار بلند " * 300,
                summary="خلاصه هوش مصنوعی بسیار بلند " * 300,
                why_it_matters="چرایی بسیار بلند " * 300,
            ),
        )

        text = build_review_item_text(item)

        self.assertLessEqual(len(text), SAFE_TELEGRAM_TEXT_LIMIT)
        self.assertIn(TRUNCATION_MARKER, text)
        self.assertIn(AI_TRUNCATION_MARKER, text)
        self.assertIn("دسته اصلی:", text)
        self.assertIn("legal", text)
        self.assertIn("فوریت:", text)
        self.assertIn("high", text)
        self.assertIn("اولویت:", text)
        self.assertIn("80", text)
        self.assertIn("اعتماد طبقه‌بندی:", text)

    def test_classification_list_displays_are_truncated_after_ai_fields(self):
        item = make_item()

        def long_labels(values):
            return [f"{value}-" + ("برچسب بلند " * 200) for value in values]

        text = build_review_item_text(
            item,
            category_labeler=long_labels,
            audience_labeler=long_labels,
            max_length=700,
        )

        self.assertLessEqual(len(text), 700)
        self.assertIn(LIST_TRUNCATION_MARKER, text)
        self.assertIn("فوریت:", text)
        self.assertIn("اولویت:", text)

    def test_small_custom_max_length_is_always_respected(self):
        item = make_item(
            candidate=make_candidate(
                title="عنوان " * 100,
                body="بدنه " * 200,
                source_name="BOE " * 100,
                source_url="https://www.boe.es/" + ("x" * 400),
            ),
            summary=make_summary(
                headline="تیتر " * 100,
                summary="خلاصه " * 100,
                why_it_matters="دلیل " * 100,
            ),
        )

        for limit in (1, 20, 80, 160):
            with self.subTest(limit=limit):
                text = build_review_item_text(item, max_length=limit)
                self.assertLessEqual(len(text), limit)

    def test_queue_display_respects_small_custom_limits(self):
        items = [
            make_item(
                candidate_id=f"candidate-{index}",
                candidate=make_candidate(
                    raw_item_id=f"raw-{index}",
                    title="عنوان خیلی بلند " * 100,
                ),
                classification=make_classification(candidate_id=f"candidate-{index}"),
            )
            for index in range(10)
        ]

        for limit in (1, 30, 120):
            with self.subTest(limit=limit):
                text, visible_items = build_review_queue_display(
                    items,
                    ReviewQueueReport(
                        pending=999999999999999999999,
                        approved=999999999999999999999,
                        rejected=999999999999999999999,
                        needs_edit=999999999999999999999,
                    ),
                    max_length=limit,
                )
                self.assertLessEqual(len(text), limit)
                if not visible_items:
                    self.assertNotIn("candidate-", text)


if __name__ == "__main__":
    unittest.main()
