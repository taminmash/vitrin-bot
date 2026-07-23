import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.radar import radar_callback, send_radar_details_message
from radar_engine.persian_detail import (
    PERSIAN_FULL_DETAIL_HEADING,
    PERSIAN_TRANSLATION_PENDING,
    TELEGRAM_SAFE_TEXT_LIMIT,
    split_telegram_text,
)
from radar_engine.renderer import render_admin_preview, render_details_page
from radar_engine.review.presentation import build_review_item_text
from tests.test_review_presentation import make_candidate, make_item, make_summary


SPANISH_BODY = "Texto oficial completo del BOE sobre residencia y trámites administrativos."
PERSIAN_BODY = "متن کامل فارسی مصوبه رسمی درباره اقامت و مراحل اداری."


def boe_radar_item(**overrides):
    item = {
        "id": "boe-1", "title": "مصوبه رسمی", "summary": "خلاصه فارسی",
        "ai_reason": "برای فارسی‌زبانان اسپانیا مهم است.", "body": SPANISH_BODY,
        "original_text": SPANISH_BODY, "type": "legal", "category": "legal",
        "source_name": "BOE", "source_url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-1",
        "structured_data": {"full_text_fa": PERSIAN_BODY}, "audience_tags": ["migration"],
        "urgency": "high",
    }
    item.update(overrides)
    return item


class BOEPersianRendererTests(unittest.TestCase):
    def test_full_detail_uses_stored_persian_translation_not_spanish_body(self):
        for renderer in (render_details_page, render_admin_preview):
            with self.subTest(renderer=renderer.__name__):
                text = renderer(boe_radar_item())
                self.assertIn(PERSIAN_FULL_DETAIL_HEADING, text)
                self.assertIn(PERSIAN_BODY, text)
                self.assertNotIn(SPANISH_BODY, text)

    def test_missing_translation_has_clear_persian_fallback(self):
        text = render_details_page(boe_radar_item(structured_data={}))
        self.assertIn(PERSIAN_TRANSLATION_PENDING, text)
        self.assertNotIn(SPANISH_BODY, text)

    def test_admin_review_selects_translated_field(self):
        item = make_item(
            candidate=make_candidate(body=SPANISH_BODY, source_key="boe", source_name="BOE"),
            summary=make_summary(structured_data={"full_text_fa": PERSIAN_BODY}),
        )
        text = build_review_item_text(item)
        self.assertIn(PERSIAN_FULL_DETAIL_HEADING, text)
        self.assertIn(PERSIAN_BODY, text)
        self.assertNotIn(SPANISH_BODY, text)

    def test_admin_review_missing_translation_never_labels_spanish_as_persian(self):
        item = make_item(
            candidate=make_candidate(body=SPANISH_BODY, source_key="boe", source_name="BOE"),
            summary=make_summary(structured_data={}),
        )
        text = build_review_item_text(item)
        self.assertIn(PERSIAN_TRANSLATION_PENDING, text)
        self.assertNotIn(SPANISH_BODY, text)


class TelegramPersianDetailSplittingTests(unittest.IsolatedAsyncioTestCase):
    def test_long_translation_splits_in_order(self):
        paragraphs = [f"بند {index} " + ("متن فارسی " * 180) for index in range(8)]
        chunks = split_telegram_text("\n\n".join(paragraphs))
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= TELEGRAM_SAFE_TEXT_LIMIT for chunk in chunks))
        combined = "\n\n".join(chunks)
        positions = [combined.index(f"بند {index}") for index in range(8)]
        self.assertEqual(positions, sorted(positions))

    async def test_navigation_buttons_are_only_on_final_message(self):
        translation = "\n\n".join("بند فارسی " + ("توضیح " * 700) for _ in range(4))
        message = SimpleNamespace(reply_text=AsyncMock())
        keyboard = object()
        with patch("handlers.radar.details_keyboard", return_value=keyboard):
            await send_radar_details_message(
                message, boe_radar_item(structured_data={"full_text_fa": translation})
            )
        calls = message.reply_text.await_args_list
        self.assertGreater(len(calls), 1)
        self.assertTrue(all(call.kwargs["reply_markup"] is None for call in calls[:-1]))
        self.assertIs(calls[-1].kwargs["reply_markup"], keyboard)
        self.assertTrue(all(len(call.args[0]) <= TELEGRAM_SAFE_TEXT_LIMIT for call in calls))

    async def test_existing_detail_callback_still_routes_to_boe_detail_sender(self):
        item = boe_radar_item()
        message = SimpleNamespace(reply_text=AsyncMock())
        query = SimpleNamespace(data="radar:details:boe-1", answer=AsyncMock(), message=message)
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})
        with (
            patch("handlers.radar.get_active_or_demo_radar_item", return_value=item),
            patch("handlers.radar.send_radar_details_message", new_callable=AsyncMock) as sender,
        ):
            await radar_callback(update, context)
        query.answer.assert_awaited_once_with()
        sender.assert_awaited_once_with(message, item)


if __name__ == "__main__":
    unittest.main()
