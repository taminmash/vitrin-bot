from pathlib import Path
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PromotionRunnerTests(unittest.TestCase):
    def test_help_runs_without_database(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_promotion.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Promote approved Radar candidates", result.stdout)

    def test_invalid_limit_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_promotion.py", "--limit", "999"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--limit must be between 1 and 200", result.stderr)


if __name__ == "__main__":
    unittest.main()

