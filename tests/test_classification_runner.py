import subprocess
import sys
import unittest


class ClassificationRunnerTests(unittest.TestCase):
    def test_help_runs_without_database_or_api_key(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_classification.py", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Run Radar AI classification", result.stdout)

    def test_invalid_limit_is_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_classification.py", "--limit", "201"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--limit must be between 1 and 200", result.stderr)


if __name__ == "__main__":
    unittest.main()
