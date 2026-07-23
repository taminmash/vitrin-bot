import argparse
import asyncio
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_report(report) -> None:
    print(f"Radar source ingestion report: {report.source_key}")
    print(f"fetched: {report.fetched_count}")
    print(f"normalized: {report.normalized_count}")
    print(f"inserted: {report.inserted_count}")
    print(f"duplicates: {report.duplicate_count}")
    print(f"updated: {report.updated_count}")
    print(f"failed: {report.failed_count}")
    if report.errors:
        print("errors:")
        for error in report.errors[:10]:
            print(f"- {error}")


async def run(source_key: str, lookback_days: int | None = None) -> int:
    from database.db import init_db
    from radar_engine.source_manager import build_default_source_manager

    init_db()
    manager = build_default_source_manager(boe_days_back=lookback_days if source_key == "boe" else None)
    report = await manager.ingest_source(source_key)
    print_report(report)
    if report.fetched_count == 0 and report.failed_count:
        return 1
    if report.normalized_count == 0 and report.failed_count >= report.fetched_count:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a manual Radar source ingestion.")
    parser.add_argument("source_key", help="Source key to ingest, for example: boe")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Override BOE lookback window for diagnostics. Safe range is clamped by the source.",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args.source_key, args.lookback_days))
    except KeyError as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
