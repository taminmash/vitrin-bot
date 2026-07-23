import unittest
from datetime import datetime, timedelta
from pathlib import Path

from radar_engine.renderer import (
    SEPARATOR,
    build_radar_deep_link,
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
        rows = channel_button_specs(sample_item(), "https://t.me/VitrinSpainBot?start=radar_radar-1", {"like": 2})
        self.assertEqual([button.text for button in rows[0]], ["🤖 مشاهده جزئیات در ویترین"])
        self.assertEqual([button.text for button in rows[1]], ["👍 پسندیدم · 2", "👎 نپسندیدم"])
        self.assertEqual(rows[0][0].url, "https://t.me/VitrinSpainBot?start=radar_radar-1")
        self.assertTrue(all(button.url or button.callback_data for row in rows for button in row))
        self.assertTrue(all(button.switch_inline_query is None for row in rows for button in row))

    def test_radar_deep_link_normalizes_bot_username_and_keeps_item_id(self):
        expected = "https://t.me/VitrinSpainBot?start=radar_6fb69d8d-4f99-432a-b887-2102570288dd"
        self.assertEqual(build_radar_deep_link("@VitrinSpainBot", "6fb69d8d-4f99-432a-b887-2102570288dd"), expected)
        self.assertEqual(build_radar_deep_link("VitrinSpainBot", "6fb69d8d-4f99-432a-b887-2102570288dd"), expected)

    def test_radar_deep_link_rejects_missing_or_invalid_bot_username(self):
        for username in (None, "", "@", "bad username", "t.me/VitrinSpainBot", "VitrinSpain"):
            with self.subTest(username=username), self.assertRaisesRegex(ValueError, "BOT_USERNAME is missing or invalid"):
                build_radar_deep_link(username, "radar-1")

    def test_details_buttons_remove_official_source_button(self):
        rows = details_button_specs(
            sample_item(),
            "https://t.me/VitrinSpainBot?start=radar_radar-1",
            "https://t.me/vitrinspain/42",
        )
        labels = [button.text for row in rows for button in row]
        self.assertEqual(labels, ["📺 بازگشت به کانال", "📤 اشتراک‌گذاری", "🏠 خانه"])
        self.assertNotIn("🔗 منبع رسمی", labels)
        self.assertEqual(rows[0][0].url, "https://t.me/vitrinspain/42")

    def test_handlers_delegate_to_shared_renderer(self):
        text = (PROJECT_ROOT / "handlers" / "radar.py").read_text(encoding="utf-8")
        self.assertIn("return render_channel_post(item)", text)
        self.assertIn("return render_details_page(item)", text)
        self.assertIn("return render_admin_preview(item)", text)
        self.assertIn("channel_button_specs(item", text)
        self.assertIn("builder(item, deep_link_for_item(item)", text)


if __name__ == "__main__":
    unittest.main()
