from __future__ import annotations

import argparse
import asyncio
from time import monotonic
from urllib.parse import urlparse
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
            started = monotonic()
            try:
                raw = await source.fetch()
            except Exception as error:
                print(f"{source.source_key}: fetched=0 normalized=0 expired_skipped=0 invalid_skipped=0 failed=1 stored=0 smoke=true duration_seconds={monotonic() - started:.2f}")
                print(f"  error: {type(error).__name__}: {error}")
                exit_code = 1
                continue
            normalized = []
            expired = invalid = 0
            for item in raw:
                try:
                    result = source.normalize(item)
                    normalized.append(result)
                    expired += int(bool(result.metadata.get("is_expired")))
                except Exception:
                    invalid += 1
            print(
                f"{source.source_key}: fetched={len(raw)} normalized={len(normalized)} "
                f"expired_skipped={expired} invalid_skipped={invalid} failed=0 stored=0 "
                f"smoke=true duration_seconds={monotonic() - started:.2f}"
            )
            for item in normalized[:3]:
                print(
                    f"  sample: id={item.external_id or '-'} title={item.original_title[:80]} "
                    f"domain={urlparse(item.source_url).netloc} published={item.published_at or '-'} "
                    f"deadline={item.valid_until or '-'} expired={bool(item.metadata.get('is_expired'))}"
                )
            continue
        manager = SourceManager()
        manager.register(source)
        report = await manager.ingest_source(source.source_key)
        print(
            f"{source.source_key}: fetched={report.fetched_count} normalized={report.normalized_count} "
            f"inserted={report.inserted_count} duplicate={report.duplicate_count} updated={report.updated_count} "
            f"expired_skipped={report.expired_skipped_count} invalid_skipped={report.invalid_skipped_count} "
            f"failed={report.failed_count} duration_seconds={report.duration_seconds:.2f}"
        )
        if report.errors:
            exit_code = 1
            for error in report.errors:
                print(f"  error: {error}")
    return exit_code


def main() -> int:
    # Source titles can contain Spanish/Persian characters. Do not let a legacy
    # Windows console code page turn an otherwise successful smoke test into an
    # encoding failure.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Run enabled Radar job sources without AI, review, promotion, or publication.")
    parser.add_argument("--source", help="Run one enabled source key.")
    parser.add_argument("--smoke", action="store_true", help="Fetch and normalize only; never write to PostgreSQL.")
    args = parser.parse_args()
    return asyncio.run(run(args.source, args.smoke))


if __name__ == "__main__":
    raise SystemExit(main())
