from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_report(report) -> None:
    print("Radar admin review queue report")
    print(f"pending={report.pending}")
    print(f"approved={report.approved}")
    print(f"rejected={report.rejected}")
    print(f"needs_edit={report.needs_edit}")
    for error in report.errors:
        print(f"error={error}")


def run(limit: int, candidate_id: str | None) -> int:
    from database.db import init_db
    from radar_engine.review.engine import RadarReviewEngine

    init_db()
    report = RadarReviewEngine().queue_report(limit=limit, candidate_id=candidate_id)
    print_report(report)
    return 0


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Show the Radar admin review queue report.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum queue candidates to inspect, 1-200.")
    parser.add_argument("--candidate-id", help="Inspect a single candidate UUID.")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 200:
        parser.error("--limit must be between 1 and 200")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.limit, args.candidate_id)


if __name__ == "__main__":
    raise SystemExit(main())
