import io
import json
import sys
import types
import unittest
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from radar_engine.ai.client import AIClient, OpenAIClient, provider_info, selected_ai_provider
from radar_engine.ai.engine import RadarAIEngine
from radar_engine.ai.models import AITaskResult, StoredAICandidate
from radar_engine.ai.providers import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidRequestError,
    AIModelUnavailableError,
    AINetworkError,
    AIProviderResponseError,
    AIQuotaError,
    AITimeoutError,
)
from radar_engine.ai.providers.gemini import DEFAULT_GEMINI_MODEL, GeminiProvider
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
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def gemini_response(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


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
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"headline": "h", "short_summary": "s", "why_it_matters": "w", "confidence": 0.8}
                        )
                    }
                }
            ]
        }
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
        payload = {"choices": [{"message": {"content": json.dumps({"headline": "h"})}}]}
        calls = [TimeoutError("timeout"), FakeResponse(payload)]

        def fake_urlopen(request, timeout):
            item = calls.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("radar_engine.ai.providers.openai.urlopen", side_effect=fake_urlopen), patch(
            "radar_engine.ai.providers.base.time.sleep"
        ):
            result = client.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual(result["headline"], "h")

    def test_timeout_failure_after_retries(self):
        client = OpenAIClient(api_key="key", model="model", max_retries=1, backoff_seconds=0)
        with patch("radar_engine.ai.providers.openai.urlopen", side_effect=TimeoutError("timeout")), patch(
            "radar_engine.ai.providers.base.time.sleep"
        ):
            with self.assertRaises(RuntimeError):
                client.complete_json([{"role": "user", "content": "x"}])

    def test_gemini_structured_response_and_json_fence(self):
        response = gemini_response(
            '```json\n{"headline":"تیتر","short_summary":"خلاصه","why_it_matters":"دلیل","confidence":0.9}\n```'
        )
        client = GeminiProvider(api_key="key", model="gemini-test", max_retries=0)
        with patch("radar_engine.ai.providers.gemini.urlopen", return_value=FakeResponse(response)):
            result = client.complete_json([{"role": "user", "content": "x"}], schema={"type": "object"})
        self.assertEqual(result["headline"], "تیتر")

    def test_gemini_generate_content_request_shape_and_headers(self):
        response = gemini_response('{"ok":true}')
        client = GeminiProvider(api_key="secret-key", model="gemini-2.5-flash-lite", max_retries=0)
        seen = {}

        def fake_urlopen(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            seen["key"] = request.get_header("X-goog-api-key")
            seen["content_type"] = request.get_header("Content-type")
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(response)

        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
        with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=fake_urlopen):
            result = client.complete_json(
                [{"role": "system", "content": "Rules"}, {"role": "user", "content": "سلام"}],
                schema=schema,
            )

        self.assertEqual(result, {"ok": True})
        self.assertIn("/v1beta/models/gemini-2.5-flash-lite:generateContent", seen["url"])
        self.assertEqual(seen["key"], "secret-key")
        self.assertEqual(seen["content_type"], "application/json")
        self.assertEqual(seen["timeout"], client.timeout_seconds)
        self.assertEqual(seen["body"]["contents"][0]["role"], "user")
        self.assertIn("SYSTEM:\nRules", seen["body"]["contents"][0]["parts"][0]["text"])
        self.assertIn("USER:\nسلام", seen["body"]["contents"][0]["parts"][0]["text"])
        generation_config = seen["body"]["generationConfig"]
        self.assertEqual(generation_config["responseMimeType"], "application/json")
        self.assertEqual(generation_config["responseJsonSchema"], schema)

    def test_gemini_rate_limit_retries_once_then_raises_quota(self):
        client = GeminiProvider(api_key="key", model="gemini-test", max_retries=3, backoff_seconds=0)
        error = HTTPError(
            "https://example.test",
            429,
            "rate limit",
            {"Retry-After": "2"},
            io.BytesIO(b'{"error":{"status":"RESOURCE_EXHAUSTED"}}'),
        )
        with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error) as urlopen_mock, patch(
            "radar_engine.ai.providers.base.time.sleep"
        ) as sleep_mock:
            with self.assertRaises(AIQuotaError):
                client.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual(urlopen_mock.call_count, 2)
        self.assertEqual(sleep_mock.call_count, 1)

    def test_gemini_zero_retries_attempts_once_on_quota_timeout_and_network(self):
        cases = [
            (
                HTTPError(
                    "https://example.test",
                    429,
                    "rate limit",
                    {"Retry-After": "2"},
                    io.BytesIO(b'{"error":{"status":"RESOURCE_EXHAUSTED"}}'),
                ),
                AIQuotaError,
            ),
            (TimeoutError("slow"), AITimeoutError),
            (URLError("network down"), AINetworkError),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                client = GeminiProvider(api_key="key", model="gemini-test", max_retries=0, backoff_seconds=0)
                with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error) as urlopen_mock, patch(
                    "radar_engine.ai.providers.base.time.sleep"
                ) as sleep_mock:
                    with self.assertRaises(expected):
                        client.complete_json([{"role": "user", "content": "x"}])
                self.assertEqual(urlopen_mock.call_count, 1)
                self.assertEqual(sleep_mock.call_count, 0)

    def test_gemini_resource_exhausted_body_is_rate_limit(self):
        client = GeminiProvider(api_key="key", model="gemini-test", max_retries=0)
        error = HTTPError(
            "https://example.test",
            400,
            "bad request",
            {},
            io.BytesIO(b'{"error":{"status":"RESOURCE_EXHAUSTED","message":"quota exceeded"}}'),
        )
        with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
            with self.assertRaises(AIQuotaError):
                client.complete_json([{"role": "user", "content": "x"}])

    def test_gemini_empty_candidates_empty_text_and_malformed_json_are_rejected(self):
        client = GeminiProvider(api_key="key", model="gemini-test", max_retries=0)
        cases = [
            {"candidates": []},
            {"candidates": [{"content": {"parts": [{"text": ""}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]},
        ]
        for response in cases:
            with self.subTest(response=response):
                with patch("radar_engine.ai.providers.gemini.urlopen", return_value=FakeResponse(response)):
                    with self.assertRaises((AIProviderResponseError, ValueError)):
                        client.complete_json([{"role": "user", "content": "x"}])

    def test_gemini_http_errors_are_classified_without_exposing_key(self):
        client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
        cases = [
            (400, AIInvalidRequestError),
            (401, AIAuthenticationError),
            (403, AIAuthenticationError),
            (404, AIModelUnavailableError),
            (429, AIQuotaError),
            (500, AINetworkError),
        ]
        for status, expected in cases:
            with self.subTest(status=status):
                error = HTTPError(
                    "https://example.test",
                    status,
                    "provider error",
                    {},
                    io.BytesIO(b'{"error":{"status":"BAD","message":"safe provider detail"}}'),
                )
                with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
                    with self.assertRaises(expected) as raised:
                        client.complete_json([{"role": "user", "content": "x"}])
                self.assertNotIn("secret-key", str(raised.exception))

    def test_gemini_http_400_provider_body_redacts_exact_api_key(self):
        client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
        error_body = json.dumps(
            {
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "message": "request rejected for secret-key",
                }
            }
        ).encode("utf-8")
        error = HTTPError("https://example.test", 400, "bad request", {}, io.BytesIO(error_body))
        with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
            with self.assertRaises(AIInvalidRequestError) as raised:
                client.complete_json([{"role": "user", "content": "x"}])
        self.assertNotIn("secret-key", str(raised.exception))
        self.assertIn("[REDACTED_API_KEY]", str(raised.exception))

    def test_gemini_http_error_logs_sanitized_diagnostics_without_changing_exception_types(self):
        cases = [
            (400, AIInvalidRequestError),
            (401, AIAuthenticationError),
            (403, AIAuthenticationError),
            (404, AIModelUnavailableError),
            (429, AIQuotaError),
            (500, AINetworkError),
        ]
        for status, expected in cases:
            with self.subTest(status=status):
                client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
                error_body = json.dumps(
                    {
                        "error": {
                            "status": "PROVIDER_STATUS",
                            "message": f"provider body mentions secret-key for status {status}",
                        }
                    }
                ).encode("utf-8")
                error = HTTPError("https://example.test", status, "provider error", {}, io.BytesIO(error_body))
                with self.assertLogs("radar_engine.ai.providers.gemini", level="WARNING") as logs:
                    with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
                        with self.assertRaises(expected):
                            client.complete_json([{"role": "user", "content": "full prompt must not be logged"}])

                text = "\n".join(logs.output)
                self.assertIn(f"status={status}", text)
                self.assertIn("https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent", text)
                self.assertIn("model=gemini-test", text)
                self.assertIn("[REDACTED_API_KEY]", text)
                self.assertNotIn("secret-key", text)
                self.assertNotIn("full prompt must not be logged", text)

    def test_gemini_http_404_logs_provider_response_body(self):
        client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
        body_text = """{
          "error": {
            "status": "NOT_FOUND",
            "message": "models/gemini-test is not found"
          }
        }"""
        error = HTTPError("https://example.test", 404, "not found", {}, io.BytesIO(body_text.encode("utf-8")))
        with self.assertLogs("radar_engine.ai.providers.gemini", level="WARNING") as logs:
            with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
                with self.assertRaises(AIModelUnavailableError):
                    client.complete_json([{"role": "user", "content": "x"}])
        text = "\n".join(logs.output)
        self.assertIn("status=404", text)
        self.assertIn("NOT_FOUND", text)
        self.assertIn("models/gemini-test is not found", text)
        self.assertIn('response_body={"error":{"status":"NOT_FOUND","message":"models/gemini-test is not found"}}', text)
        self.assertNotIn("\n          ", text)

    def test_gemini_multiline_json_error_log_is_one_line_and_redacted(self):
        client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
        body_text = """{
          "error": {
            "status": "INVALID_ARGUMENT",
            "message": "bad secret-key request"
          }
        }"""
        error = HTTPError("https://example.test", 400, "bad request", {}, io.BytesIO(body_text.encode("utf-8")))
        with self.assertLogs("radar_engine.ai.providers.gemini", level="WARNING") as logs:
            with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
                with self.assertRaises(AIInvalidRequestError):
                    client.complete_json([{"role": "user", "content": "x"}])
        text = "\n".join(logs.output)
        self.assertIn(
            'response_body={"error":{"status":"INVALID_ARGUMENT","message":"bad [REDACTED_API_KEY] request"}}',
            text,
        )
        self.assertNotIn("secret-key", text)
        self.assertNotIn("\n          ", text)

    def test_gemini_non_json_error_log_collapses_whitespace(self):
        client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
        body_text = "first line\r\n   second\t\tline\nthird secret-key"
        error = HTTPError("https://example.test", 400, "bad request", {}, io.BytesIO(body_text.encode("utf-8")))
        with self.assertLogs("radar_engine.ai.providers.gemini", level="WARNING") as logs:
            with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
                with self.assertRaises(AIInvalidRequestError):
                    client.complete_json([{"role": "user", "content": "x"}])
        text = "\n".join(logs.output)
        self.assertIn("response_body=first line second line third [REDACTED_API_KEY]", text)
        self.assertNotIn("secret-key", text)
        self.assertNotIn("\r", text)
        self.assertNotIn("\nthird", text)

    def test_gemini_http_error_log_body_is_bounded(self):
        client = GeminiProvider(api_key="secret-key", model="gemini-test", max_retries=0)
        long_body = "x" * 700
        error = HTTPError("https://example.test", 400, "bad request", {}, io.BytesIO(long_body.encode("utf-8")))
        with self.assertLogs("radar_engine.ai.providers.gemini", level="WARNING") as logs:
            with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=error):
                with self.assertRaises(AIInvalidRequestError):
                    client.complete_json([{"role": "user", "content": "x"}])
        text = "\n".join(logs.output)
        self.assertIn("response_body=" + ("x" * 500), text)
        self.assertNotIn("x" * 501, text)

    def test_gemini_timeout_is_classified(self):
        client = GeminiProvider(api_key="key", model="gemini-test", max_retries=0)
        with patch("radar_engine.ai.providers.gemini.urlopen", side_effect=TimeoutError("slow")):
            with self.assertRaises(AITimeoutError):
                client.complete_json([{"role": "user", "content": "x"}])

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
        self.assertEqual(result.prompt_version, "radar-structured-v2")

    def test_summarizer_extracts_job_fields_and_normalizes_support_values(self):
        class Client:
            model = "test-model"

            def complete_json(self, messages, schema=None):
                return {
                    "category": "JOB",
                    "job_title": "مهندس",
                    "employer": "شرکت",
                    "city": "Madrid",
                    "region": None,
                    "salary": None,
                    "contract_type": "Full-time",
                    "working_hours": None,
                    "deadline": None,
                    "requirements": ["Python"],
                    "language_level": None,
                    "job_level": "Senior",
                    "experience_required": "5 years",
                    "visa_sponsorship": "yes",
                    "relocation_support": "not stated",
                    "apply_from_outside_spain": "NO",
                    "why_it_matters": "فرصت تخصصی",
                    "source_url": None,
                    "confidence": 0.9,
                }

        result = RadarAISummarizer(Client()).summarize(make_candidate())
        self.assertEqual(result.structured_data["category"], "job")
        self.assertEqual(result.structured_data["visa_sponsorship"], "YES")
        self.assertEqual(result.structured_data["relocation_support"], "UNKNOWN")
        self.assertEqual(result.structured_data["apply_from_outside_spain"], "NO")
        self.assertEqual(result.structured_data["source_url"], "https://www.boe.es/test")


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

    def test_rate_limit_stops_batch_without_marking_failed(self):
        candidates = [
            StoredAICandidate(candidate_id="c1", candidate=make_candidate()),
            StoredAICandidate(candidate_id="c2", candidate=make_candidate()),
        ]
        failed = []
        stored = []

        class Summarizer:
            calls = 0

            def summarize(self, candidate):
                self.calls += 1
                raise AIQuotaError("Gemini quota or rate limit exceeded")

        summarizer = Summarizer()
        engine = RadarAIEngine(
            summarizer=summarizer,
            load_candidates=lambda limit, candidate_id=None: candidates,
            store_result=lambda candidate_id, result: stored.append(candidate_id),
            mark_failed=lambda candidate_id, error: failed.append((candidate_id, error)),
        )
        with self.assertLogs("radar_engine.ai.engine", level="WARNING") as logs:
            report = engine.run()
        self.assertEqual(summarizer.calls, 1)
        self.assertEqual(report.processed, 1)
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.failed, 0)
        self.assertEqual(report.rate_limited, 1)
        self.assertEqual(report.remaining, 2)
        self.assertTrue(report.stopped_early)
        self.assertEqual(stored, [])
        self.assertEqual(failed, [])
        self.assertEqual(
            "\n".join(logs.output).count("Gemini rate limit reached. Remaining AI jobs postponed to next cycle."),
            1,
        )


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
        self.assertIn("structured_data", sql)
        self.assertIn("%s::jsonb", sql)
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
        self.assertIn("actionability_gate", sql)
