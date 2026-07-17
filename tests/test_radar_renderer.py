import unittest
from datetime import datetime, timedelta
from pathlib import Path

from radar_engine.renderer import (
    SEPARATOR,
    channel_button_specs,
    details_button_specs,
    location_text,
    render_admin_preview,
    render_channel_post,
    render_details_page,
    render_ready_preview,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sample_item(**overrides):
    today = datetime(2026, 7, 13)
    item = {
        "id": "radar-1",
        "title": "فستیوال تابستانی آخر هفته",
        "summary": "یک رویداد خانوادگی کوتاه برای آخر هفته در مادرید معرفی شده است.",
        "ai_reason": "برای خانواده‌ها و تازه‌واردها راه خوبی برای شناخت شهر است.",
        "body": "جزئیات کامل برنامه، ساعت حضور، شرایط ثبت‌نام و نکات لازم برای شرکت‌کنندگان در این بخش می‌آید.",
        "type": "event",
        "category": "event",
        "city": "کل اسپانیا",
        "province": "Spain",
        "country": "Spain",
        "start_date": today,
        "end_date": today + timedelta(days=7),
        "source_name": "Eventbrite España",
        "source_url": "https://www.eventbrite.es/e/example",
        "urgency": "medium",
        "audience_tags": ["family", "all"],
        "content_status": "ready",
    }
    item.update(overrides)
    return item


class RadarRendererTests(unittest.TestCase):
    def test_renderers_share_clean_template_sections(self):
        item = sample_item()
        for text in (
            render_channel_post(item),
            render_details_page(item),
            render_admin_preview(item),
            render_ready_preview(item),
        ):
            self.assertIn("🛰️ رادار اسپانیا", text)
            self.assertIn("🎉 فستیوال تابستانی آخر هفته", text)
            self.assertIn(SEPARATOR, text)
            self.assertIn("📝 خلاصه", text)
            self.assertIn("💡 چرا مهم است؟", text)

    def test_channel_post_is_short_and_keeps_source_name_only(self):
        item = sample_item()
        text = render_channel_post(item)
        self.assertIn("Eventbrite España", text)
        self.assertNotIn(item["body"], text)
        self.assertNotIn(item["source_url"], text)
        self.assertLess(len(text.split()), 80)

    def test_details_page_contains_full_source_inline(self):
        item = sample_item()
        text = render_details_page(item)
        self.assertIn("📄 جزئیات کامل", text)
        self.assertIn(item["body"], text)
        self.assertIn("🔗 منبع رسمی", text)
        self.assertIn(item["source_name"], text)
        self.assertIn(item["source_url"], text)

    def test_metadata_is_localized_and_deduplicates_spain(self):
        item = sample_item(city="کل اسپانیا", province="Spain", country="Spain")
        text = render_details_page(item)
        self.assertEqual(location_text(item), "کل اسپانیا")
        self.assertIn("📍 محدوده: کل اسپانیا", text)
        self.assertNotIn("Spain / کل اسپانیا / Spain", text)
        self.assertIn("🏷 دسته: رویداد", text)
        self.assertIn("🎯 مناسب برای: همه فارسی‌زبانان اسپانیا", text)
        self.assertIn("⚡ فوریت: معمولی", text)
        self.assertIn("⏳ اعتبار: 2026-07-13 تا 2026-07-20", text)

    def test_internal_status_values_are_translated(self):
        text = render_admin_preview(sample_item(content_status="ready"))
        self.assertIn("وضعیت: آماده انتشار", text)
        self.assertNotIn("وضعیت: ready", text)

    def test_channel_buttons_match_requested_layout(self):
        rows = channel_button_specs(
            sample_item(),
            "https://t.me/VitrinSpainBot?start=radar_radar-1",
            {"like": 2},
            "https://t.me/share/url?url=example&text=full",
        )
        self.assertEqual([button.text for button in rows[0]], ["📄 مشاهده جزئیات"])
        self.assertEqual([button.text for button in rows[1]], ["📤 اشتراک‌گذاری"])
        self.assertEqual([button.text for button in rows[2]], ["👍 پسندیدم · 2", "👎 نپسندیدم"])
        self.assertEqual(rows[0][0].url, "https://t.me/VitrinSpainBot?start=radar_radar-1")
        self.assertIn("text=full", rows[1][0].url)

    def test_details_buttons_remove_official_source_button(self):
        rows = details_button_specs(
            sample_item(),
            "https://t.me/VitrinSpainBot?start=radar_radar-1",
            "https://t.me/vitrinspain/42",
        )
        labels = [button.text for row in rows for button in row]
        self.assertEqual(labels, ["📤 اشتراک‌گذاری", "⬅️ صفحه قبل", "🏠 صفحه اصلی"])
        self.assertNotIn("🔗 منبع رسمی", labels)
        self.assertEqual(rows[1][0].callback_data, "radar:type:event")

    def test_handlers_delegate_to_shared_renderer(self):
        text = (PROJECT_ROOT / "handlers" / "radar.py").read_text(encoding="utf-8")
        self.assertIn("return render_channel_post(item)", text)
        self.assertIn("return render_details_page(item)", text)
        self.assertIn("return render_admin_preview(item)", text)
        self.assertIn("channel_button_specs(item", text)
        self.assertIn("details_button_specs(", text)


if __name__ == "__main__":
    unittest.main()
