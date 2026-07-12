from __future__ import annotations

from dataclasses import dataclass, field


PUBLICATION_STATUS_VALUES = ("published", "failed")
RESULT_STATUS_VALUES = (
    "published",
    "already_published",
    "validation_failed",
    "telegram_failed",
    "telegram_ambiguous",
    "persistence_failed_reconciliation_required",
    "failed",
    "dry_run",
)


def _clean(value) -> str:
    return ("" if value is None else str(value)).strip()


@dataclass
class EligiblePublicationItem:
    item: dict

    def __post_init__(self) -> None:
        if not isinstance(self.item, dict):
            raise ValueError("item must be a dictionary")
        item_id = _clean(self.item.get("id"))
        if not item_id:
            raise ValueError("item id must not be blank")
        self.item["id"] = item_id

    @property
    def id(self) -> str:
        return self.item["id"]


@dataclass
class TelegramPublicationResponse:
    channel_id: str
    telegram_message_id: int
    channel_post_url: str | None = None

    def __post_init__(self) -> None:
        self.channel_id = _clean(self.channel_id)
        if not self.channel_id:
            raise ValueError("channel_id must not be blank")
        self.telegram_message_id = int(self.telegram_message_id)
        if self.telegram_message_id <= 0:
            raise ValueError("telegram_message_id must be positive")
        self.channel_post_url = _clean(self.channel_post_url) or None


@dataclass
class PublicationResult:
    radar_item_id: str
    status: str
    telegram_message_id: int | None = None
    channel_id: str | None = None
    channel_post_url: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        self.radar_item_id = _clean(self.radar_item_id)
        if not self.radar_item_id:
            raise ValueError("radar_item_id must not be blank")
        self.status = _clean(self.status)
        if self.status not in RESULT_STATUS_VALUES:
            raise ValueError(f"unsupported publication result status: {self.status}")
        if self.telegram_message_id is not None:
            self.telegram_message_id = int(self.telegram_message_id)
        self.channel_id = _clean(self.channel_id) or None
        self.channel_post_url = _clean(self.channel_post_url) or None
        self.error = _clean(self.error) or None

    @property
    def published(self) -> bool:
        return self.status == "published"

    @property
    def already_published(self) -> bool:
        return self.status == "already_published"

    @property
    def reconciliation_required(self) -> bool:
        return self.status == "persistence_failed_reconciliation_required"


@dataclass
class PublicationReport:
    loaded: int = 0
    processed: int = 0
    published: int = 0
    already_published: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

