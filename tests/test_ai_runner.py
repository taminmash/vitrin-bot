from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
import io
import os
import subprocess
import sys
import unittest

from radar_engine.ai.providers import AIAuthenticationError
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

    def test_provider_smoke_test_makes_one_safe_provider_call(self):
        provider = FakeSmokeProvider()
        buffer = io.StringIO()
        with patch("radar_engine.ai.client.build_ai_provider", return_value=provider):
            with redirect_stdout(buffer):
                code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 0)
        self.assertEqual(provider.calls, 1)
        output = buffer.getvalue()
        self.assertIn("AI provider: gemini", output)
        self.assertIn("AI model: gemini-2.5-flash-lite", output)
        self.assertIn("Smoke test result: success", output)

    def test_provider_smoke_test_auth_failure_never_prints_key(self):
        provider = FakeSmokeProvider(error=AIAuthenticationError("bad secret-key"))
        buffer = io.StringIO()
        with patch("radar_engine.ai.client.build_ai_provider", return_value=provider):
            with redirect_stdout(buffer):
                code = run_radar_ai.provider_smoke_test()

        self.assertEqual(code, 4)
        self.assertEqual(provider.calls, 1)
        output = buffer.getvalue()
        self.assertIn("Smoke test result: authentication failed", output)
        self.assertNotIn("secret-key", output)
