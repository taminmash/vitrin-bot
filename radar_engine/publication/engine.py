from __future__ import annotations

import logging

from radar_engine.publication.models import EligiblePublicationItem, PublicationReport, PublicationResult
from radar_engine.publication.publisher import (
    AmbiguousTelegramFailure,
    DefiniteTelegramFailure,
    PublicationValidationError,
    validate_publication_item,
)


logger = logging.getLogger(__name__)


class RadarPublicationEngine:
    def __init__(
        self,
        loader=None,
        publisher=None,
        success_recorder=None,
        failure_recorder=None,
        existing_success_loader=None,
        existing_message_loader=None,
    ):
        if loader is None or success_recorder is None or failure_recorder is None or existing_success_loader is None or existing_message_loader is None:
            from radar_engine.publication.storage import (
                get_existing_successful_publication,
                get_radar_item_channel_message,
                load_ready_publication_items,
                record_publication_failure,
                record_publication_success,
            )

            loader = loader or load_ready_publication_items
            success_recorder = success_recorder or record_publication_success
            failure_recorder = failure_recorder or record_publication_failure
            existing_success_loader = existing_success_loader or get_existing_successful_publication
            existing_message_loader = existing_message_loader or get_radar_item_channel_message
        self.loader = loader
        self.publisher = publisher
        self.success_recorder = success_recorder
        self.failure_recorder = failure_recorder
        self.existing_success_loader = existing_success_loader
        self.existing_message_loader = existing_message_loader

    async def publish_item(
        self,
        item: EligiblePublicationItem,
        dry_run: bool = False,
        published_by: int | None = None,
    ) -> PublicationResult:
        existing = self.existing_success_loader(item.id)
        if existing:
            return PublicationResult(item.id, "already_published", telegram_message_id=existing.get("telegram_message_id"))
        existing_message = self.existing_message_loader(item.id)
        if existing_message:
            return PublicationResult(item.id, "already_published", telegram_message_id=existing_message.get("channel_message_id"))
        validation_errors = validate_publication_item(item.item, channel_id="dry-run-channel" if dry_run else "pending")
        if validation_errors:
            return PublicationResult(item.id, "validation_failed", error=str(validation_errors))
        if dry_run:
            return PublicationResult(item.id, "dry_run")
        if self.publisher is None:
            raise RuntimeError("publisher is required for real publication")
        try:
            response = await self.publisher.publish(item)
        except PublicationValidationError as error:
            return PublicationResult(item.id, "validation_failed", error=str(error))
        except AmbiguousTelegramFailure as error:
            return PublicationResult(item.id, "telegram_ambiguous", error=str(error))
        except DefiniteTelegramFailure as error:
            self.failure_recorder(item.id, getattr(self.publisher, "channel_id", ""), str(error), published_by=published_by)
            return PublicationResult(item.id, "telegram_failed", error=str(error))
        try:
            return self.success_recorder(item.id, response, published_by=published_by)
        except Exception as error:
            logger.exception(
                "Radar publication persistence failed after send item_id=%s channel_id=%s message_id=%s",
                item.id,
                response.channel_id,
                response.telegram_message_id,
            )
            return PublicationResult(
                item.id,
                "persistence_failed_reconciliation_required",
                telegram_message_id=response.telegram_message_id,
                channel_id=response.channel_id,
                channel_post_url=response.channel_post_url,
                error=str(error),
            )

    async def run(
        self,
        limit: int = 20,
        radar_item_id: str | None = None,
        include_failed: bool = False,
        dry_run: bool = False,
        published_by: int | None = None,
    ) -> PublicationReport:
        safe_limit = max(1, min(int(limit), 20))
        report = PublicationReport()
        items = self.loader(limit=safe_limit, radar_item_id=radar_item_id, include_failed=include_failed)
        report.loaded = len(items)
        for item in items:
            report.processed += 1
            try:
                result = await self.publish_item(item, dry_run=dry_run, published_by=published_by)
                if result.published or result.status == "dry_run":
                    report.published += 1
                elif result.already_published:
                    report.already_published += 1
                elif result.status == "validation_failed":
                    report.skipped += 1
                    report.errors.append(f"{item.id}: {result.error}")
                else:
                    report.failed += 1
                    report.errors.append(f"{item.id}: {result.status}: {result.error or ''}".strip())
            except Exception as error:
                logger.exception("Radar publication failed for item %s", item.id)
                report.failed += 1
                report.errors.append(f"{item.id}: {error}")
        return report
