import json
import sys
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from radar_engine.ai.client import AIClient, OpenAIClient, provider_info, selected_ai_provider
from radar_engine.ai.providers import AIConfigurationError
from radar_engine.ai.providers.gemini import DEFAULT_GEMINI_MODEL, GeminiProvider
from radar_engine.ai.engine import RadarAIEngine
from radar_engine.ai.models import AITaskResult, StoredAICandidate
from radar_engine.ai.summarizer import RadarAISummarizer
from radar_engine.ai.storage import load_pending_ai_candidates, store_ai_result
from tests.test_radar_candidate import make_candidate


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class AIClientTests(unittest.TestCase):
    def test_provider_selection_defaults_to_gemini_and_rejects_invalid(self):
        self.assertEqual(selected_ai_provider(None), "gemini")
        self.assertEqual(selected_ai_provider("openai"), "openai")
        with self.assertRaises(AIConfigurationError):
            selected_ai_provider("anthropic")

    def test_provider_info_uses_selected_provider_without_exposing_key(self):
        with patch.dict("os.environ", {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "secret"}, clear=False):
            info = provider_info()
        self.assertEqual(info.provider, "gemini")
        self.assertEqual(info.model, DEFAULT_GEMINI_MODEL)
        self.assertTrue(info.configured)

    def test_successful_structured_response(self):
        payload = {"choices": [{"message": {"content": json.dumps({"headline": "h", "short_summary": "s", "why_it_matters": "w", "confidence": 0.8})}}]}
        client = OpenAIClient(api_key="key", model="model", max_retries=0)
        with patch("radar_engine.ai.providers.openai.urlopen", return_value=FakeResponse(payload)):
            result = client.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual(result["headline"], "h")

    def test_invalid_json_and_empty_response_are_rejected(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=0)
        invalid = {"choices": [{"message": {"content": "not-json"}}]}
        with patch("radar_engine.ai.providers.openai.urlopen", return_value=FakeResponse(invalid)):
            with self.assertRaises(ValueError):
                client.complete_json([{"role": "user", "content": "x"}])
        empty = {"choices": [{"message": {"content": ""}}]}
        with patch("radar_engine.ai.providers.openai.urlopen", return_value=FakeResponse(empty)):
            with self.assertRaises(ValueError):
                client.complete_json([{"role": "user", "content": "x"}])

    def test_retry_logic_for_timeout(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=1, backoff_seconds=0)
        payload = {"choices": [{"message": {"content": json.dumps({"headline": "h", "short_summary": "s", "why_it_matters": "w", "confidence": 0.8})}}]}
        calls = [TimeoutError("timeout"), FakeResponse(payload)]

        def fake_urlopen(request, timeout):
            item = calls.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("radar_engine.ai.providers.openai.urlopen", side_effect=fake_urlopen), patch("radar_engine.ai.providers.base.time.sleep"):
            result = client.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual(result["headline"], "h")

    def test_timeout_failure_after_retries(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=1, backoff_seconds=0)
        with patch("radar_engine.ai.providers.openai.urlopen", side_effect=TimeoutError("timeout")), patch("radar_engine.ai.providers.base.time.sleep"):
            with self.assertRaises(RuntimeError):
                client.complete_json([{"role": "user", "content": "x"}])

    def test_gemini_structured_response_and_json_fence(self):
        response = {"output_text": "```json\n{\"headline\":\"تیتر\",\"short_summary\":\"خلاصه\",\"why_it_matters\":\"دلیل\",\"confidence\":0.9}\n```"}
        client = GeminiProvider(api_key="key", model="gemini-test", max_retries=0)
        with patch("radar_engine.ai.providers.gemini.urlopen", return_value=FakeResponse(response)):
            result = client.complete_json([{"role": "user", "content": "x"}], schema={"type": "object"})
        self.assertEqual(result["headline"], "تیتر")

    def test_default_ai_client_uses_configured_provider(self):
        class Provider:
            model = "m"
            provider_name = "test"

            def complete_json(self, messages, schema=None):
                return {"ok": True}

        client = AIClient(Provider())
        self.assertEqual(client.model, "m")
        self.assertEqual(client.provider_name, "test")
        self.assertEqual(client.complete_json([], schema={"type": "object"}), {"ok": True})


class AISummarizerTests(unittest.TestCase):
    def test_summarizer_validates_json_payload(self):
        class Client:
            model = "test-model"

            def complete_json(self, messages):
                return {"headline": "تیتر", "short_summary": "خلاصه", "why_it_matters": "دلیل", "confidence": 0.9}

        result = RadarAISummarizer(Client()).summarize(make_candidate())
        self.assertEqual(result.model_name, "test-model")
        self.assertEqual(result.prompt_version, "radar-summary-v1")


class AIEngineTests(unittest.TestCase):
    def test_engine_report_success_dry_run_and_failure(self):
        candidate = StoredAICandidate(candidate_id="c1", candidate=make_candidate())

        class Summarizer:
            def summarize(self, candidate):
                return AITaskResult("h", "s", "w", 0.9, "model", "radar-summary-v1", 1)

        stored = []
        engine = RadarAIEngine(
            summarizer=Summarizer(),
            load_candidates=lambda limit, candidate_id=None: [candidate],
            store_result=lambda candidate_id, result: stored.append(candidate_id),
            mark_failed=lambda candidate_id, error: None,
        )
        report = engine.run(dry_run=True)
        self.assertEqual(report.loaded, 1)
        self.assertEqual(report.completed, 1)
        self.assertEqual(stored, [])

        report = engine.run(dry_run=False)
        self.assertEqual(report.completed, 1)
        self.assertEqual(stored, ["c1"])

    def test_engine_report_failure_marks_failed(self):
        candidate = StoredAICandidate(candidate_id="c1", candidate=make_candidate())
        failed = []

        class Summarizer:
            def summarize(self, candidate):
                raise RuntimeError("bad ai")

        engine = RadarAIEngine(
            summarizer=Summarizer(),
            load_candidates=lambda limit, candidate_id=None: [candidate],
            store_result=lambda candidate_id, result: None,
            mark_failed=lambda candidate_id, error: failed.append((candidate_id, error)),
        )
        report = engine.run()
        self.assertEqual(report.failed, 1)
        self.assertEqual(failed[0][0], "c1")


class FakeCursor:
    def __init__(self, rows=None):
        self.executed = []
        self.rows = rows or []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


class AIStorageTests(unittest.TestCase):
    def test_store_ai_result_writes_result_without_candidate_status_update(self):
        cursor = FakeCursor()
        db = types.ModuleType("database.db")

        @contextmanager
        def db_cursor(dict_cursor=False):
            yield None, cursor

        db.db_cursor = db_cursor
        result = AITaskResult("h", "s", "w", 0.8, "model", "radar-summary-v1", 12)
        with patch.dict(sys.modules, {"database.db": db}):
            store_ai_result("candidate-1", result)
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("radar_ai_results", sql)
        self.assertIn("ON CONFLICT (candidate_id) DO NOTHING", sql)
        self.assertNotIn("UPDATE radar_candidates", sql)
        self.assertNotIn("ai_completed", sql)

    def test_loader_skips_candidates_with_existing_ai_result(self):
        cursor = FakeCursor()
        db = types.ModuleType("database.db")

        @contextmanager
        def db_cursor(dict_cursor=False):
            yield None, cursor

        db.db_cursor = db_cursor
        with patch.dict(sys.modules, {"database.db": db}):
            self.assertEqual(load_pending_ai_candidates(candidate_id="candidate-1"), [])
        sql = "\n".join(statement for statement, _ in cursor.executed)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("radar_ai_results", sql)
