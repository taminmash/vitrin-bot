import unittest
from datetime import datetime

from radar_engine.classification.models import RadarClassificationResult
from radar_engine.pipeline.candidate import RadarCandidate
from radar_engine.promotion.mapper import map_approved_source_to_radar_item, validate_mapped_payload
from radar_engine.promotion.models import ApprovedPromotionSource, MappedRadarItemPayload
from radar_engine.review.models import RadarSummaryForReview


def make_source(**overrides):
    candidate = overrides.pop(
        "candidate",
        RadarCandidate(
            raw_item_id="raw-1",
            source_key="boe",
            source_name="BOE",
            external_id="external-1",
            title="Original title",
            body="Official original body",
            language="es",
            source_url="https://www.boe.es/test",
            canonical_url="https://www.boe.es/test",
            published_at=datetime(2026, 7, 1, 9, 0),
            valid_from=datetime(2026, 7, 2, 0, 0),
            valid_until=datetime(2026, 7, 9, 0, 0),
            source_category="Government",
            source_location="Spain",
            source_type="official",
            trust_level=5,
            country="Spain",
            metadata={},
        ),
    )
    summary = overrides.pop(
        "summary",
        RadarSummaryForReview(
            ai_result_id="ai-1",
            headline="AI headline",
            summary="AI short summary",
            why_it_matters="AI reason",
            confidence=0.9,
        ),
    )
    classification = overrides.pop(
        "classification",
        RadarClassificationResult(
            candidate_id="candidate-1",
            primary_category="legal",
            category_tags=["legal", "education"],
            audience_tags=["migration", "student"],
            cities=[],
            geographic_scope="national",
            urgency="high",
            priority_score=80,
            confidence=0.8,
            model_name="model",
            prompt_version="radar-classification-v1",
            processing_time_ms=10,
        ),
    )
    data = {
        "candidate_id": "candidate-1",
        "review_id": "review-1",
        "review_status": "approved",
        "candidate": candidate,
        "summary": summary,
        "classification": classification,
    }
    data.update(overrides)
    return ApprovedPromotionSource(**data)


class PromotionMapperTests(unittest.TestCase):
    def test_maps_reviewed_ai_output_to_existing_radar_schema(self):
        payload = map_approved_source_to_radar_item(make_source())
        fields = payload.fields

        self.assertEqual(payload.content_status, "ready")
        self.assertEqual(fields["title"], "AI headline")
        self.assertEqual(fields["summary"], "AI short summary")
        self.assertEqual(fields["ai_summary"], "AI short summary")
        self.assertEqual(fields["ai_reason"], "AI reason")
        self.assertEqual(fields["body"], "Official original body")
        self.assertEqual(fields["original_text"], "Official original body")
        self.assertEqual(fields["type"], "legal")
        self.assertEqual(fields["category"], "legal")
        self.assertEqual(fields["category_tags"], ["legal", "education"])
        self.assertEqual(fields["audience_tags"], ["migration", "student"])
        self.assertIsNone(fields["city"])
        self.assertIsNone(fields["province"])
        self.assertEqual(fields["urgency"], "high")
        self.assertEqual(fields["priority_score"], 80)
        self.assertEqual(fields["ai_priority"], 80)
        self.assertEqual(fields["source_name"], "BOE")
        self.assertEqual(fields["source_url"], "https://www.boe.es/test")
        self.assertEqual(fields["start_date"], datetime(2026, 7, 2, 0, 0))
        self.assertEqual(fields["end_date"], datetime(2026, 7, 9, 0, 0))
        self.assertNotIn("is_published", fields)
        self.assertNotIn("published_at", fields)

    def test_city_scope_preserves_first_city(self):
        classification = make_source().classification
        classification.cities = ["Madrid"]
        classification.geographic_scope = "city"
        fields = map_approved_source_to_radar_item(make_source(classification=classification)).fields
        self.assertEqual(fields["city"], "Madrid")
        self.assertEqual(fields["province"], "Madrid")

    def test_boe_promotion_preserves_spanish_original_and_persian_translation(self):
        source = make_source(
            summary=RadarSummaryForReview(
                ai_result_id="ai-translation",
                headline="تیتر فارسی",
                summary="خلاصه فارسی",
                why_it_matters="دلیل فارسی",
                confidence=0.9,
                structured_data={"full_text_fa": "ترجمه کامل فارسی متن رسمی"},
            )
        )
        fields = map_approved_source_to_radar_item(source).fields
        self.assertEqual(fields["body"], "Official original body")
        self.assertEqual(fields["original_text"], "Official original body")
        self.assertEqual(fields["original_language"], "es")
        self.assertEqual(fields["structured_data"]["full_text_fa"], "ترجمه کامل فارسی متن رسمی")

    def test_invalid_controlled_value_and_blank_output_rejected(self):
        payload = MappedRadarItemPayload(
            fields={
                "title": "Title",
                "summary": "Summary",
                "type": "invalid",
                "category": "invalid",
                "source_url": "https://example.com",
                "source_name": "Source",
                "urgency": "high",
            }
        )
        errors = validate_mapped_payload(payload)
        self.assertEqual(errors[0]["field"], "type")
        blank = MappedRadarItemPayload(
            fields={
                "title": "Title",
                "summary": " ",
                "type": "legal",
                "category": "legal",
                "source_url": " ",
                "source_name": "Source",
                "urgency": "high",
            }
        )
        self.assertEqual({error["code"] for error in validate_mapped_payload(blank)}, {"blank_summary", "blank_source_url"})


if __name__ == "__main__":
    unittest.main()
