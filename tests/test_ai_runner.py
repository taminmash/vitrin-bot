from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
import io
import os
import subprocess
import sys
import types
import unittest

from radar_engine.ai.providers import AIAuthenticationError, AINetworkError, AIQuotaError
from scripts import run_radar_ai


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeSmokeProvider:
    provider_name = "gemini"
    model_name = "gemini-2.5-flash-lite"
    model = "gemini-2.5-flash-lite"

    def __init__(self, result=None, error=None):
        self.result = result or {"ok": True, "message": "سلام"}
        self.error = error
        self.calls = 0

    def complete_json(self, messages, schema=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class FakeGeminiProvider:
    instances = []

    def __init__(self, api_key=None, model=None, max_retries=None, result=None, error=None):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.result = result or {"ok": True, "message": "سلام"}
        self.error = error
        self.calls = 0
        FakeGeminiProvider.instances.append(self)

    def complete_json(self, messages, schema=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class AIRunnerTests(unittest.TestCase):
    def test_help_runs_without_database(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_ai.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run Radar AI summarization", result.stdout)
        self.assertIn("--check-provider", result.stdout)
        self.assertIn("--provider-smoke-test", result.stdout)

    def test_check_provider_runs_without_database(self):
        env = os.environ.copy()
        env.update({"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"})
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_ai.py", "--check-provider"],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("AI provider: gemini", result.stdout)
        self.assertIn("Automatic batch limit: 1", result.stdout)
        self.assertIn("Request delay seconds: 15.0", result.stdout)
        self.assertIn("API key configured: yes", result.stdout)
        self.assertNotIn("test-key", result.stdout)

    def test_invalid_limit_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_ai.py", "--limit", "999"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--limit must be between 1 and 200", result.stderr)

    def test_provider_smoke_test_directly_uses_gemini_regardless_of_ai_provider(self):
        FakeGeminiProvider.instances = []
        buffer = io.StringIO()
        env = {
            "AI_PROVIDER": "openai",
            "GEMINI_API_KEY": "gemini-secret",
            "GEMINI_MODEL": "gemini-custom",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("scripts.run_radar_ai.GeminiProvider", FakeGeminiProvider):
                with patch("radar_engine.ai.client.build_ai_provider", side_effect=AssertionError("OpenAI path used")):
                    fake_db = types.SimpleNamespace(init_db=lambda: (_ for _ in ()).throw(AssertionError("database initialized")))
                    with patch.dict(sys.modules, {"database.db": fake_db}):
                        with redirect_stdout(buffer):
                            code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 0)
        self.assertEqual(len(FakeGeminiProvider.instances), 1)
        provider = FakeGeminiProvider.instances[0]
        self.assertEqual(provider.calls, 1)
        self.assertEqual(provider.api_key, "gemini-secret")
        self.assertEqual(provider.model, "gemini-custom")
        self.assertEqual(provider.max_retries, 0)
        output = buffer.getvalue()
        self.assertIn("AI provider: gemini", output)
        self.assertIn("AI model: gemini-custom", output)
        self.assertIn("Smoke test result: success", output)
        self.assertNotIn("gemini-secret", output)

    def test_provider_smoke_test_auth_failure_never_prints_key(self):
        class AuthFailureGemini(FakeGeminiProvider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, error=AIAuthenticationError("bad secret-key"), **kwargs)

        FakeGeminiProvider.instances = []
        buffer = io.StringIO()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-key"}, clear=False):
            with patch("scripts.run_radar_ai.GeminiProvider", AuthFailureGemini):
                with redirect_stdout(buffer):
                    code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 4)
        provider = FakeGeminiProvider.instances[0]
        self.assertEqual(provider.calls, 1)
        output = buffer.getvalue()
        self.assertIn("Smoke test result: authentication failed", output)
        self.assertNotIn("secret-key", output)

    def test_provider_smoke_test_missing_gemini_key_is_safe(self):
        buffer = io.StringIO()
        with patch.dict(os.environ, {"AI_PROVIDER": "openai"}, clear=True):
            with redirect_stdout(buffer):
                code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 6)
        output = buffer.getvalue()
        self.assertIn("AI provider: gemini", output)
        self.assertIn("AI model: gemini-2.5-flash-lite", output)
        self.assertIn("Smoke test result: missing configuration", output)

    def test_provider_smoke_test_reports_network_failures_safely(self):
        class NetworkFailureGemini(FakeGeminiProvider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, error=AINetworkError("temporary secret-key outage"), **kwargs)

        FakeGeminiProvider.instances = []
        buffer = io.StringIO()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-key"}, clear=False):
            with patch("scripts.run_radar_ai.GeminiProvider", NetworkFailureGemini):
                with redirect_stdout(buffer):
                    code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 8)
        self.assertEqual(FakeGeminiProvider.instances[0].max_retries, 0)
        output = buffer.getvalue()
        self.assertIn("Smoke test result: network or provider server failure", output)
        self.assertNotIn("secret-key", output)

    def test_provider_smoke_test_reports_quota_safely(self):
        class QuotaGemini(FakeGeminiProvider):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, error=AIQuotaError("quota for secret-key"), **kwargs)

        FakeGeminiProvider.instances = []
        buffer = io.StringIO()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-key"}, clear=False):
            with patch("scripts.run_radar_ai.GeminiProvider", QuotaGemini):
                with redirect_stdout(buffer):
                    code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 2)
        self.assertEqual(FakeGeminiProvider.instances[0].calls, 1)
        output = buffer.getvalue()
        self.assertIn("Smoke test result: quota/rate limited", output)
        self.assertNotIn("secret-key", output)
