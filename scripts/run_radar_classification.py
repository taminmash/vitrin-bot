from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_report(report) -> None:
    print("Radar AI classification report")
    print(f"loaded={report.loaded}")
    print(f"processed={report.processed}")
    print(f"completed={report.completed}")
    print(f"failed={report.failed}")
    print(f"skipped={report.skipped}")
    for error in report.errors:
        print(f"error={error}")


def run(limit: int, candidate_id: str | None, dry_run: bool) -> int:
    from database.db import init_db
    from radar_engine.classification.engine import RadarClassificationEngine

    init_db()
    report = RadarClassificationEngine().run(
        limit=limit,
        candidate_id=candidate_id,
        dry_run=dry_run,
    )
    print_report(report)
    return 0


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run Radar AI classification for summarized candidates.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum candidates to process, 1-200.")
    parser.add_argument("--candidate-id", help="Process a single candidate UUID.")
    parser.add_argument("--dry-run", action="store_true", help="Call AI and validate output without writing results.")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 200:
        parser.error("--limit must be between 1 and 200")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.limit, args.candidate_id, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
