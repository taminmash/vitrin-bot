from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Publish explicitly selected ready Radar items.")
    parser.add_argument("--radar-item-id", help="Publish one Radar item UUID.")
    parser.add_argument("--publish-ready", action="store_true", help="Publish a bounded batch of ready items.")
    parser.add_argument("--confirm-publish", action="store_true", help="Required for real batch publication.")
    parser.add_argument("--include-failed", action="store_true", help="Include failed items for explicit retry.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum ready items for batch mode, 1-20.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without sending Telegram messages or writing DB state.")
    parser.add_argument("--reconcile", action="store_true", help="Record an already-sent Telegram message without resending.")
    parser.add_argument("--release-attempt", action="store_true", help="Release an uncertain attempt only after confirming no Telegram message was sent.")
    parser.add_argument("--confirm-not-sent", action="store_true", help="Required with --release-attempt.")
    parser.add_argument("--telegram-message-id", type=int, help="Telegram message ID for reconciliation.")
    parser.add_argument("--channel-id", help="Telegram channel ID for reconciliation.")
    parser.add_argument("--channel-post-url", help="Optional channel post URL for reconciliation.")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    if args.reconcile and args.release_attempt:
        parser.error("--reconcile and --release-attempt cannot be used together")
    if args.reconcile:
        missing = []
        if not args.radar_item_id:
            missing.append("--radar-item-id")
        if not args.telegram_message_id:
            missing.append("--telegram-message-id")
        if not args.channel_id:
            missing.append("--channel-id")
        if missing:
            parser.error("--reconcile requires " + ", ".join(missing))
    elif args.release_attempt:
        missing = []
        if not args.radar_item_id:
            missing.append("--radar-item-id")
        if not args.confirm_not_sent:
            missing.append("--confirm-not-sent")
        if missing:
            parser.error("--release-attempt requires " + ", ".join(missing))
    elif args.publish_ready:
        if not args.dry_run and not args.confirm_publish:
            parser.error("--publish-ready requires --confirm-publish unless --dry-run is used")
    elif not args.radar_item_id:
        parser.error("provide --radar-item-id, --publish-ready, --reconcile, or --release-attempt")
    return args


async def run(args):
    from database.db import init_db

    init_db()
    if args.reconcile:
        from radar_engine.publication.storage import reconcile_publication

        result = reconcile_publication(
            args.radar_item_id,
            args.telegram_message_id,
            args.channel_id,
            channel_post_url=args.channel_post_url,
        )
        print(f"status={result.status}")
        print(f"radar_item_id={result.radar_item_id}")
        print(f"telegram_message_id={result.telegram_message_id or '-'}")
        return 0
    if args.release_attempt:
        from radar_engine.publication.storage import release_publication_attempt

        result = release_publication_attempt(args.radar_item_id)
        print(f"status={result.status}")
        print(f"radar_item_id={result.radar_item_id}")
        if result.error:
            print(f"error={result.error}")
        return 0 if result.status == "attempt_released" else 1

    publisher = None
    if not args.dry_run:
        from config_v2 import BOT_TOKEN, CHANNEL_VITRIN, CHANNEL_VITRIN_USERNAME
        from telegram import Bot
        from handlers.radar import channel_post_keyboard, format_radar_channel_post
        from radar_engine.publication.publisher import RadarTelegramPublisher

        if not BOT_TOKEN:
            print("BOT_TOKEN is not configured", file=sys.stderr)
            return 2
        publisher = RadarTelegramPublisher(
            Bot(BOT_TOKEN),
            channel_id=CHANNEL_VITRIN,
            channel_username=CHANNEL_VITRIN_USERNAME,
            renderer=format_radar_channel_post,
            keyboard_builder=channel_post_keyboard,
        )

    from radar_engine.publication.engine import RadarPublicationEngine

    report = await RadarPublicationEngine(publisher=publisher).run(
        limit=args.limit,
        radar_item_id=args.radar_item_id,
        include_failed=args.include_failed,
        dry_run=args.dry_run,
    )
    print(f"loaded={report.loaded}")
    print(f"processed={report.processed}")
    print(f"published={report.published}")
    print(f"already_published={report.already_published}")
    print(f"skipped={report.skipped}")
    print(f"failed={report.failed}")
    if report.errors:
        print("errors:")
        for error in report.errors:
            print(f"- {error}")
    return 0


def main(argv=None):
    args = parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
