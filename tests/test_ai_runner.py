from pathlib import Path
import os
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
