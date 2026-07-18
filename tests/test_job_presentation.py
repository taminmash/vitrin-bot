import unittest

from radar_engine.category_headers import CATEGORY_HEADERS, category_header
from radar_engine.ai.summarizer import SUMMARY_SCHEMA
from radar_engine.job_presentation import JOB_HELP_TEXT, job_card, radar_score
from radar_engine.renderer import render_admin_preview, render_channel_post, render_details_page
from radar_engine.review.presentation import build_review_item_text
from tests.test_review_presentation import make_candidate, make_classification, make_item, make_summary


def structured(**overrides):
    data = {
        "category": "job",
        "job_title": "مهندس نرم‌افزار",
        "employer": "شرکت نمونه",
        "city": "Madrid",
        "region": "Comunidad de Madrid",
        "salary": "€35,000–€42,000",
        "contract_type": "تمام‌وقت",
        "working_hours": "40 ساعت در هفته",
        "deadline": "2026-08-31",
        "requirements": ["Python", "سه سال سابقه"],
        "language_level": "Spanish B2",
        "job_level": "Mid-level",
        "experience_required": "3 years",
        "visa_sponsorship": "YES",
        "relocation_support": "NO",
        "apply_from_outside_spain": "YES",
        "why_it_matters": "فرصت مناسب برای متخصصان فارسی‌زبان",
        "source_url": "https://www.boe.es/job-1",
    }
    data.update(overrides)
    return data


def review_item(data=None):
    return make_item(
        candidate=make_candidate(title="BOE empleo publico", source_url="https://www.boe.es/job-1"),
        summary=make_summary(structured_data=data or {}, why_it_matters="دلیل مهم بودن"),
        classification=make_classification(primary_category="job", category_tags=["job"], cities=["Madrid"]),
    )


class JobPresentationTests(unittest.TestCase):
    def test_reusable_category_header_infrastructure_is_complete(self):
        self.assertEqual(category_header("job"), "🟢 آگهی استخدام رایگان")
        self.assertEqual(
            set(CATEGORY_HEADERS),
            {
                "job", "job_seeker", "grant", "scholarship", "rental", "property",
                "free_course", "event", "notice", "urgent_alert", "discount",
            },
        )

    def test_boe_job_with_salary_is_structured(self):
        text = build_review_item_text(review_item(structured()))
        self.assertIn("⭐ امتیاز Radar\n95 / 100", text)
        self.assertIn("🟢 آگهی استخدام رایگان", text)
        self.assertIn("💶 حقوق\n€35,000–€42,000", text)
        self.assertIn("🛂 Visa Sponsorship\nبله", text)

    def test_job_without_salary_hides_field(self):
        self.assertNotIn("💶 حقوق", job_card(structured(salary=None)))

    def test_job_without_deadline_hides_field(self):
        self.assertNotIn("📅 مهلت درخواست", job_card(structured(deadline=None)))

    def test_job_without_language_hides_field(self):
        self.assertNotIn("🗣 سطح زبان", job_card(structured(language_level=None)))

    def test_job_without_sponsorship_shows_no(self):
        text = job_card(structured(visa_sponsorship="NO"))
        self.assertIn("🛂 Visa Sponsorship\nخیر", text)

    def test_unknown_values_are_hidden_not_printed(self):
        text = job_card(
            structured(
                visa_sponsorship="UNKNOWN",
                relocation_support="UNKNOWN",
                apply_from_outside_spain="UNKNOWN",
            )
        )
        self.assertNotIn("Unknown", text)
        self.assertNotIn("UNKNOWN", text)
        self.assertNotIn("Visa Sponsorship", text)

    def test_legacy_pending_job_remains_reviewable(self):
        text = build_review_item_text(review_item())
        self.assertIn("🟢 آگهی استخدام رایگان", text)
        self.assertIn("عنوان شغل", text)
        self.assertIn("Madrid", text)
        self.assertIn("https://www.boe.es/job-1", text)
        self.assertNotIn("Unknown", text)

    def test_admin_review_and_preview_use_full_card(self):
        text = render_admin_preview({"type": "job", "structured_data": structured(), "body": "x" * 2000})
        self.assertNotIn("x" * 100, text)
        self.assertIn("مهندس نرم‌افزار", text)
        self.assertIn("🌍 استان / منطقه", text)
        self.assertIn("🕒 ساعت کاری", text)
        self.assertIn("🎓 پیش‌نیازها", text)
        self.assertIn("👔 سطح شغلی", text)
        self.assertIn("📈 سابقه موردنیاز", text)
        self.assertIn("✈️ Relocation Support", text)

    def test_radar_score_hides_when_no_inputs_exist(self):
        self.assertIsNone(radar_score({}, None, {}))

    def test_optional_why_it_matters_is_hidden(self):
        data = structured(why_it_matters=None)
        text = job_card(data)
        self.assertNotIn("چرا این فرصت مهم است؟", text)
        self.assertIn("null", SUMMARY_SCHEMA["properties"]["why_it_matters"]["type"])
        self.assertNotIn("why_it_matters", SUMMARY_SCHEMA["required"])

    def test_confidence_never_appears_in_job_renderers(self):
        item = review_item(structured())
        review = build_review_item_text(item)
        detail = render_details_page({"type": "job", "structured_data": structured()})
        channel = render_channel_post({"type": "job", "structured_data": structured()})
        for text in (review, detail, channel):
            self.assertNotIn("confidence", text.casefold())
            self.assertNotIn("اعتماد", text)

    def test_help_text_is_detail_only_never_channel(self):
        item = {"type": "job", "structured_data": structured()}
        details = render_details_page(item)
        channel = render_channel_post(item)
        self.assertIn(JOB_HELP_TEXT, details)
        self.assertNotIn("نیاز به کمک برای ارسال درخواست", channel)

    def test_job_channel_post_contains_only_requested_short_card(self):
        data = structured(
            full_description="شرح کامل شغل",
            duties="توسعه و نگهداری سامانه",
            remote_status="Hybrid",
        )
        text = render_channel_post(
            {
                "type": "job",
                "title": "عنوان نرمال‌شده",
                "body": "متن کامل منبع",
                "source_name": "BOE",
                "source_url": "https://www.boe.es/job-1",
                "structured_data": data,
            }
        )
        self.assertEqual(
            text,
            "🟢 آگهی استخدام رایگان\n\n"
            "💼 عنوان شغل\nمهندس نرم‌افزار\n\n"
            "📍 شهر\nMadrid\n\n"
            "📄 نوع قرارداد\nتمام‌وقت\n\n"
            "🗣 پیش‌نیازها / زبان موردنیاز\nPython • سه سال سابقه\n\n"
            "⏳ مهلت ارسال درخواست\n2026-08-31",
        )
        for excluded in (
            "شرکت نمونه", "Visa Sponsorship", "امکان اقدام از خارج اسپانیا",
            "چرا این فرصت مهم است؟", "https://www.boe.es/job-1", "متن کامل منبع",
            "شرح کامل شغل", "€35,000", "40 ساعت", "Hybrid", "BOE",
        ):
            self.assertNotIn(excluded, text)

    def test_job_channel_post_uses_required_missing_field_fallbacks(self):
        text = render_channel_post(
            {
                "type": "job",
                "title": "عنوان نرمال‌شده",
                "structured_data": structured(
                    job_title=None,
                    city=None,
                    contract_type=None,
                    requirements=None,
                    language_level=None,
                ),
            }
        )
        self.assertIn("💼 عنوان شغل\nعنوان نرمال‌شده", text)
        self.assertIn("📍 شهر\nنامشخص", text)
        self.assertIn("📄 نوع قرارداد\nنامشخص", text)
        self.assertIn("🗣 پیش‌نیازها / زبان موردنیاز\nذکر نشده", text)

    def test_job_channel_prefers_requirements_then_language(self):
        requirements = render_channel_post(
            {"type": "job", "structured_data": structured(requirements=["Python"], language_level="Spanish B2")}
        )
        language = render_channel_post(
            {"type": "job", "structured_data": structured(requirements=None, language_level="Spanish B2")}
        )
        self.assertIn("موردنیاز\nPython", requirements)
        self.assertNotIn("Spanish B2", requirements)
        self.assertIn("موردنیاز\nSpanish B2", language)

    def test_full_job_detail_keeps_extended_fields_and_hides_empty_ones(self):
        text = render_details_page(
            {
                "type": "job",
                "body": "شرح کامل موقعیت و مسئولیت‌ها",
                "source_name": "InfoJobs",
                "structured_data": structured(
                    duties="توسعه سرویس‌های Python",
                    education="کارشناسی",
                    remote_status="Hybrid",
                    relocation_support=None,
                ),
            }
        )
        self.assertIn("📝 توضیحات کامل\nشرح کامل موقعیت و مسئولیت‌ها", text)
        self.assertIn("📋 وظایف\nتوسعه سرویس‌های Python", text)
        self.assertIn("🎓 تحصیلات\nکارشناسی", text)
        self.assertIn("🏠 وضعیت دورکاری\nHybrid", text)
        self.assertIn("🏷 نام منبع\nInfoJobs", text)
        self.assertNotIn("✈️ Relocation Support", text)

    def test_non_job_channel_renderer_keeps_existing_template(self):
        text = render_channel_post(
            {
                "type": "event",
                "title": "رویداد مادرید",
                "summary": "خلاصه رویداد",
                "ai_reason": "برای کاربران مفید است",
                "source_name": "Eventbrite",
            }
        )
        self.assertIn("🛰️ رادار اسپانیا", text)
        self.assertIn("📝 خلاصه", text)
        self.assertIn("💡 چرا مهم است؟", text)
        self.assertIn("🔗 منبع رسمی", text)


if __name__ == "__main__":
    unittest.main()
