from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def run(source_key: str | None, smoke: bool) -> int:
    from radar_engine.source_config import BLOCKED_SOURCES, configured_job_sources
    from radar_engine.source_manager import SourceManager

    sources = configured_job_sources()
    if source_key:
        sources = [source for source in sources if source.source_key == source_key]
    if not sources:
        print("No enabled/configured job source matched.")
        for item in BLOCKED_SOURCES:
            print(f"{item.key}: {item.status} - {item.reason}")
        return 2
    exit_code = 0
    for source in sources:
        if smoke:
            raw = await source.fetch()
            normalized = [source.normalize(item) for item in raw]
            print(f"{source.source_key}: fetched={len(raw)} normalized={len(normalized)} stored=0 smoke=true")
            continue
        manager = SourceManager()
        manager.register(source)
        report = await manager.ingest_source(source.source_key)
        print(
            f"{source.source_key}: fetched={report.fetched_count} normalized={report.normalized_count} "
            f"inserted={report.inserted_count} duplicate={report.duplicate_count} updated={report.updated_count} "
            f"failed={report.failed_count}"
        )
        if report.errors:
            exit_code = 1
            for error in report.errors:
                print(f"  error: {error}")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run enabled Radar job sources without AI, review, promotion, or publication.")
    parser.add_argument("--source", help="Run one enabled source key.")
    parser.add_argument("--smoke", action="store_true", help="Fetch and normalize only; never write to PostgreSQL.")
    args = parser.parse_args()
    return asyncio.run(run(args.source, args.smoke))


if __name__ == "__main__":
    raise SystemExit(main())
