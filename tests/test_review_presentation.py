import unittest

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.review.models import RadarReviewQueueItem, RadarSummaryForReview, ReviewQueueReport
from radar_engine.review.presentation import (
    QUEUE_MORE_ITEMS_NOTE,
    SAFE_TELEGRAM_TEXT_LIMIT,
    TRUNCATION_MARKER,
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
        "metadata": {},
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


if __name__ == "__main__":
    unittest.main()
