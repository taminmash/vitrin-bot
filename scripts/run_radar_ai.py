import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def print_report(report) -> None:
    print("Radar AI summarization report")
    print(f"loaded: {report.loaded}")
    print(f"processed: {report.processed}")
    print(f"completed: {report.completed}")
    print(f"failed: {report.failed}")
    if report.errors:
        print("errors:")
        for error in report.errors[:10]:
            print(f"- {error}")


def run(limit: int, candidate_id: str | None, dry_run: bool) -> int:
    from database.db import init_db
    from radar_engine.ai.client import provider_info
    from radar_engine.ai.engine import RadarAIEngine

    init_db()
    info = provider_info()
    print(f"AI provider: {info.provider}")
    print(f"AI model: {info.model}")
    report = RadarAIEngine().run(limit=limit, candidate_id=candidate_id, dry_run=dry_run)
    print_report(report)
    return 0 if report.loaded or not report.failed else 1


def check_provider() -> int:
    from radar_engine.ai.client import provider_info

    info = provider_info()
    print(f"AI provider: {info.provider}")
    print(f"AI model: {info.model}")
    print(f"API key configured: {'yes' if info.configured else 'no'}")
    return 0 if info.configured else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Radar AI summarization for pending candidates.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum candidates to process, 1-200.")
    parser.add_argument("--candidate-id", help="Process a single candidate UUID.")
    parser.add_argument("--dry-run", action="store_true", help="Call AI and validate output without writing results.")
    parser.add_argument("--check-provider", action="store_true", help="Validate AI provider configuration without using the database.")
    args = parser.parse_args()
    if args.check_provider:
        return check_provider()
    if args.limit < 1 or args.limit > 200:
        parser.error("--limit must be between 1 and 200")
    return run(args.limit, args.candidate_id, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
