import subprocess
import sys
import unittest


class ReviewRunnerTests(unittest.TestCase):
    def test_help_runs_without_database(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_review_queue.py", "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Show the Radar admin review queue report", result.stdout)

    def test_invalid_limit_is_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_review_queue.py", "--limit", "201"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--limit must be between 1 and 200", result.stderr)


if __name__ == "__main__":
    unittest.main()
