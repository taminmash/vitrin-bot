import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_report(report) -> None:
    print("Radar candidate pipeline report")
    print(f"loaded: {report.loaded_count}")
    print(f"processed: {report.processed_count}")
    print(f"created: {report.created_count}")
    print(f"existing: {report.already_exists_count}")
    print(f"rejected: {report.rejected_count}")
    print(f"failed: {report.failed_count}")
    if report.errors:
        print("errors:")
        for error in report.errors[:10]:
            print(f"- {error}")


def run(limit: int) -> int:
    from database.db import init_db
    from radar_engine.pipeline.engine import RadarCandidatePipeline

    init_db()
    report = RadarCandidatePipeline().run(limit=limit)
    print_report(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic Radar raw-to-candidate pipeline.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum raw rows to process, 1-500.")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 500:
        parser.error("--limit must be between 1 and 500")
    return run(args.limit)


if __name__ == "__main__":
    sys.exit(main())
