from pathlib import Path
import subprocess
import sys
import unittest

from scripts.run_radar_publication import parse_args


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PublicationRunnerTests(unittest.TestCase):
    def test_help_runs_without_database(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_publication.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Publish explicitly selected ready Radar items", result.stdout)

    def test_batch_requires_explicit_confirm_unless_dry_run(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_publication.py", "--publish-ready"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--publish-ready requires --confirm-publish", result.stderr)
        args = parse_args(["--publish-ready", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_invalid_limit_rejected(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_publication.py", "--publish-ready", "--dry-run", "--limit", "999"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--limit must be between 1 and 20", result.stderr)

    def test_reconcile_requires_existing_message_identifiers(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_publication.py", "--reconcile", "--radar-item-id", "radar-1"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--reconcile requires --telegram-message-id, --channel-id", result.stderr)

    def test_release_attempt_requires_explicit_confirm_not_sent(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_radar_publication.py", "--release-attempt", "--radar-item-id", "radar-1"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--release-attempt requires --confirm-not-sent", result.stderr)

    def test_release_attempt_parse_is_explicit_and_never_reconcile(self):
        args = parse_args(["--release-attempt", "--radar-item-id", "radar-1", "--confirm-not-sent"])
        self.assertTrue(args.release_attempt)
        self.assertTrue(args.confirm_not_sent)
        with self.assertRaises(SystemExit):
            parse_args(
                [
                    "--release-attempt",
                    "--reconcile",
                    "--radar-item-id",
                    "radar-1",
                    "--confirm-not-sent",
                    "--telegram-message-id",
                    "1",
                    "--channel-id",
                    "@vitrin",
                ]
            )


if __name__ == "__main__":
    unittest.main()
