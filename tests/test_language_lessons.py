import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.ext import ApplicationHandlerStop

from handlers.language_lessons import (
    FEEDBACK_STATE_KEY,
    MAX_FEEDBACK_LENGTH,
    PLACEHOLDER_TEXTS,
    build_language_lesson_keyboard,
    format_persian_number,
    language_lesson_callback,
    language_lesson_feedback_handler,
    parse_lesson_callback,
)


def callback_update(data, chat_type="private"):
    message = SimpleNamespace(reply_text=AsyncMock())
    query = SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=123),
        message=message,
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
    )
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(type=chat_type)), query


def message_update(text):
    return SimpleNamespace(message=SimpleNamespace(text=text, reply_text=AsyncMock()), effective_user=SimpleNamespace(id=123, full_name=""))


class LessonKeyboardTests(unittest.TestCase):
    def test_persian_digit_reaction_labels_start_at_zero(self):
        self.assertEqual(format_persian_number(12), "۱۲")
        keyboard = build_language_lesson_keyboard("a1", 1, 0, 0)
        self.assertEqual(keyboard.inline_keyboard[2][0].text, "👍 پسندیدم · ۰")
        self.assertEqual(keyboard.inline_keyboard[2][1].text, "👎 نپسندیدم · ۰")


class LessonCallbackParsingTests(unittest.TestCase):
    def test_valid_callback_parsing(self):
        parsed = parse_lesson_callback("lesson:react:like:a1_test-2:12")
        self.assertEqual((parsed.action, parsed.reaction, parsed.level, parsed.lesson_number), ("react", "like", "a1_test-2", 12))

    def test_malformed_callbacks_are_rejected(self):
        for data in (None, "lesson:unknown:a1:1", "lesson:react:maybe:a1:1", "lesson:quiz:a1", "other:a1:1"):
            self.assertIsNone(parse_lesson_callback(data))

    def test_invalid_level_and_lesson_number_are_rejected(self):
        self.assertIsNone(parse_lesson_callback("lesson:quiz:UPPER:1"))
        self.assertIsNone(parse_lesson_callback("lesson:quiz:" + "a" * 17 + ":1"))
        self.assertIsNone(parse_lesson_callback("lesson:quiz:a1:0"))
        self.assertIsNone(parse_lesson_callback("lesson:quiz:a1:-1"))


class LessonHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_placeholder_routing(self):
        update, query = callback_update("lesson:quiz:a1:1")
        await language_lesson_callback(update, SimpleNamespace(user_data={}))
        query.answer.assert_awaited_once_with()
        query.message.reply_text.assert_awaited_once_with(PLACEHOLDER_TEXTS["quiz"])

    @patch("handlers.language_lessons.get_language_lesson_reaction_counts", return_value={"like": 1, "dislike": 0})
    @patch("handlers.language_lessons.save_language_lesson_reaction")
    async def test_like_persistence(self, save, _counts):
        update, query = callback_update("lesson:react:like:a1:1", "channel")
        await language_lesson_callback(update, SimpleNamespace(user_data={}))
        save.assert_called_once_with(123, "a1", 1, "like")
        query.answer.assert_awaited_once_with("نظر مثبت شما ثبت شد ✅")

    @patch("handlers.language_lessons.get_language_lesson_reaction_counts", return_value={"like": 0, "dislike": 1})
    @patch("handlers.language_lessons.save_language_lesson_reaction")
    async def test_dislike_and_reaction_switching(self, save, _counts):
        context = SimpleNamespace(user_data={})
        for data in ("lesson:react:like:a1:1", "lesson:react:dislike:a1:1"):
            update, _ = callback_update(data, "channel")
            await language_lesson_callback(update, context)
        self.assertEqual(save.call_args_list[-1].args, (123, "a1", 1, "dislike"))

    @patch("handlers.language_lessons.get_language_lesson_reaction_counts", return_value={"like": 1, "dislike": 0})
    @patch("handlers.language_lessons.save_language_lesson_reaction")
    async def test_duplicate_reaction_is_delegated_to_upsert(self, save, _counts):
        context = SimpleNamespace(user_data={})
        for _ in range(2):
            update, _ = callback_update("lesson:react:like:a1:1", "channel")
            await language_lesson_callback(update, context)
        self.assertEqual(save.call_count, 2)

    async def test_channel_comment_and_report_redirect_to_deep_link(self):
        for action in ("comment", "report"):
            update, query = callback_update(f"lesson:{action}:a1:4", "channel")
            await language_lesson_callback(update, SimpleNamespace(user_data={}))
            query.answer.assert_awaited_once_with(url=f"https://t.me/VitrinSpainBot?start=lesson-{action}-a1-4")

    async def test_comment_and_report_create_feedback_state(self):
        for action in ("comment", "report"):
            context = SimpleNamespace(user_data={})
            update, query = callback_update(f"lesson:{action}:a1:4")
            await language_lesson_callback(update, context)
            self.assertEqual(context.user_data[FEEDBACK_STATE_KEY]["action"], action)
            query.message.reply_text.assert_awaited()

    async def test_feedback_length_validation_and_unrelated_messages(self):
        unrelated_context = SimpleNamespace(user_data={})
        unrelated = message_update("hello")
        await language_lesson_feedback_handler(unrelated, unrelated_context)
        unrelated.message.reply_text.assert_not_awaited()

        context = SimpleNamespace(user_data={FEEDBACK_STATE_KEY: {"action": "comment", "level": "a1", "lesson_number": 1}})
        update = message_update("x" * (MAX_FEEDBACK_LENGTH + 1))
        with self.assertRaises(ApplicationHandlerStop):
            await language_lesson_feedback_handler(update, context)
        self.assertIn(FEEDBACK_STATE_KEY, context.user_data)

    @patch("handlers.language_lessons.publish_lesson_comment", new_callable=AsyncMock, return_value=False)
    @patch("handlers.language_lessons.save_language_lesson_comment", return_value={"id": 1, "level": "a1", "lesson_number": 1, "comment_text": "great lesson", "display_name": ""})
    async def test_successful_comment_clears_state(self, save, _publish):
        context = SimpleNamespace(user_data={FEEDBACK_STATE_KEY: {"action": "comment", "level": "a1", "lesson_number": 1}})
        update = message_update("great lesson")
        with self.assertRaises(ApplicationHandlerStop):
            await language_lesson_feedback_handler(update, context)
        save.assert_called_once_with(123, "a1", 1, "great lesson", "")
        self.assertNotIn(FEEDBACK_STATE_KEY, context.user_data)

    @patch("handlers.language_lessons.notify_lesson_report", new_callable=AsyncMock)
    @patch("handlers.language_lessons.save_language_lesson_report", return_value={"level": "a1", "lesson_number": 1, "report_text": "video has no sound"})
    async def test_successful_report_clears_state(self, save, _notify):
        context = SimpleNamespace(user_data={FEEDBACK_STATE_KEY: {"action": "report", "level": "a1", "lesson_number": 1}})
        update = message_update("video has no sound")
        with self.assertRaises(ApplicationHandlerStop):
            await language_lesson_feedback_handler(update, context)
        save.assert_called_once_with(123, "a1", 1, "video has no sound")
        self.assertNotIn(FEEDBACK_STATE_KEY, context.user_data)
