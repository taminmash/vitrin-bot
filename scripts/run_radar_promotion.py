from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Promote approved Radar candidates into ready Radar items.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum candidates to promote, 1-200.")
    parser.add_argument("--candidate-id", help="Promote or inspect a single candidate UUID.")
    parser.add_argument("--dry-run", action="store_true", help="Map and validate without writing radar_items.")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 200:
        parser.error("--limit must be between 1 and 200")
    return args


def main(argv=None):
    args = parse_args(argv)
    if not args.dry_run:
        from database.db import init_db

        init_db()
    from radar_engine.promotion.engine import RadarPromotionEngine

    report = RadarPromotionEngine().run(
        limit=args.limit,
        candidate_id=args.candidate_id,
        dry_run=args.dry_run,
    )
    print(f"loaded={report.loaded}")
    print(f"processed={report.processed}")
    print(f"created={report.created}")
    print(f"already_promoted={report.already_promoted}")
    print(f"rejected={report.rejected}")
    print(f"failed={report.failed}")
    if report.errors:
        print("errors:")
        for error in report.errors:
            print(f"- {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
