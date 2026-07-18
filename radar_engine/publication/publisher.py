from __future__ import annotations

from radar_engine.publication.models import EligiblePublicationItem, TelegramPublicationResponse


TELEGRAM_TEXT_LIMIT = 4096


class PublicationValidationError(ValueError):
    pass


class DefiniteTelegramFailure(RuntimeError):
    pass


class AmbiguousTelegramFailure(RuntimeError):
    pass


def _clean(value) -> str:
    return ("" if value is None else str(value)).strip()


def is_expired(item: dict) -> bool:
    from radar_engine.job_expiration import job_temporal_state

    if (item.get("type") or item.get("category")) == "job":
        return job_temporal_state(item).expired
    from datetime import datetime

    now = datetime.now()
    for key in ("expires_at", "end_date"):
        value = item.get(key)
        if value and hasattr(value, "__le__") and value <= now:
            return True
    return False


def validate_publication_item(item: dict, rendered_text: str | None = None, channel_id=None) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not _clean(item.get("title")):
        errors.append({"field": "title", "code": "blank_title", "message": "title is required"})
    if not (_clean(item.get("summary")) or _clean(item.get("ai_summary"))):
        errors.append({"field": "summary", "code": "blank_summary", "message": "summary is required"})
    if item.get("content_status") != "ready":
        errors.append({"field": "content_status", "code": "not_ready", "message": "item must be ready"})
    if (item.get("channel_status") or "not_sent") not in {"not_sent", "failed"}:
        errors.append({"field": "channel_status", "code": "invalid_channel_status", "message": "item is not sendable"})
    if bool(item.get("is_published")):
        errors.append({"field": "is_published", "code": "already_public", "message": "item is already public"})
    if item.get("channel_message_id"):
        errors.append({"field": "channel_message_id", "code": "already_sent", "message": "item already has a Telegram message"})
    if is_expired(item):
        from radar_engine.job_expiration import EXPIRED_PUBLICATION_MESSAGE

        errors.append({"field": "expires_at", "code": "expired", "message": EXPIRED_PUBLICATION_MESSAGE})
    if channel_id in (None, "", 0):
        errors.append({"field": "channel_id", "code": "missing_channel", "message": "Telegram channel is not configured"})
    if rendered_text is not None:
        if not _clean(rendered_text):
            errors.append({"field": "rendered_text", "code": "empty_render", "message": "rendered post is empty"})
        if len(rendered_text) > TELEGRAM_TEXT_LIMIT:
            errors.append({"field": "rendered_text", "code": "too_long", "message": "rendered post exceeds Telegram limit"})
    return errors


def build_channel_post_url(channel_id, message_id: int, channel_username: str | None = None) -> str | None:
    username = _clean(channel_username)
    if username.startswith("@"):
        username = username[1:]
    if username:
        return f"https://t.me/{username}/{int(message_id)}"
    channel_text = _clean(channel_id)
    if channel_text.startswith("@"):
        return f"https://t.me/{channel_text[1:]}/{int(message_id)}"
    return None


class RadarTelegramPublisher:
    def __init__(
        self,
        bot,
        channel_id=None,
        channel_username: str | None = None,
        renderer=None,
        keyboard_builder=None,
    ):
        self.bot = bot
        self.channel_id = channel_id
        self.channel_username = channel_username
        self.renderer = renderer
        self.keyboard_builder = keyboard_builder

    def _renderer(self):
        if self.renderer:
            return self.renderer
        from handlers.radar import format_radar_channel_post

        return format_radar_channel_post

    def _keyboard_builder(self):
        if self.keyboard_builder:
            return self.keyboard_builder
        from handlers.radar import channel_post_keyboard

        return channel_post_keyboard

    async def publish(self, item: EligiblePublicationItem) -> TelegramPublicationResponse:
        channel_id = self.channel_id
        if channel_id is None:
            from config_v2 import CHANNEL_VITRIN

            channel_id = CHANNEL_VITRIN
        channel_username = self.channel_username
        if channel_username is None:
            try:
                from config_v2 import CHANNEL_VITRIN_USERNAME
            except Exception:
                CHANNEL_VITRIN_USERNAME = None
            channel_username = CHANNEL_VITRIN_USERNAME

        rendered_text = self._renderer()(item.item)
        errors = validate_publication_item(item.item, rendered_text, channel_id=channel_id)
        if errors:
            raise PublicationValidationError(str(errors))

        try:
            message = await self.bot.send_message(
                chat_id=channel_id,
                text=rendered_text,
                reply_markup=self._keyboard_builder()(item.item),
                disable_web_page_preview=True,
                read_timeout=20,
                write_timeout=20,
            )
        except Exception as error:
            if error.__class__.__name__ in {"TimedOut", "TimeoutError"}:
                raise AmbiguousTelegramFailure(str(error)) from error
            raise DefiniteTelegramFailure(str(error)) from error

        message_id = int(getattr(message, "message_id"))
        return TelegramPublicationResponse(
            channel_id=str(channel_id),
            telegram_message_id=message_id,
            channel_post_url=build_channel_post_url(channel_id, message_id, channel_username),
        )
