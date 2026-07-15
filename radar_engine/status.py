from __future__ import annotations

from datetime import datetime, timezone
import os
import subprocess

from radar_engine.ai.client import provider_info
from radar_engine.scheduler import ai_batch_limit_from_env, ai_request_delay_seconds_from_env


UNKNOWN = "Unknown"


def _display(value) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    text = str(value).strip()
    return text or UNKNOWN


def current_utc_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_commit_version() -> str:
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA"):
        value = os.getenv(key)
        if value:
            return value[:12]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            text=True,
            capture_output=True,
            timeout=2,
            check=True,
        )
        return result.stdout.strip() or UNKNOWN
    except Exception:
        return UNKNOWN


def ai_provider_status() -> dict[str, str]:
    try:
        info = provider_info()
        return {"provider": _display(info.provider), "model": _display(info.model)}
    except Exception:
        return {"provider": UNKNOWN, "model": UNKNOWN}


def ai_queue_status(provider: str | None = None) -> dict[str, str]:
    try:
        batch_limit = ai_batch_limit_from_env(provider=provider)
    except Exception:
        batch_limit = UNKNOWN
    try:
        delay_seconds = ai_request_delay_seconds_from_env(provider=provider)
    except Exception:
        delay_seconds = UNKNOWN
    return {
        "batch_limit": _display(batch_limit),
        "delay_seconds": _display(delay_seconds),
    }


def scheduler_status(application=None) -> str:
    bot_data = getattr(application, "bot_data", None) or {}
    scheduler = bot_data.get("radar_boe_scheduler")
    task = bot_data.get("radar_boe_scheduler_task")
    if scheduler and task and not getattr(task, "done", lambda: True)():
        return "Running"
    return UNKNOWN


def build_radar_status_text(
    *,
    metrics: dict | None,
    scheduler: str = UNKNOWN,
    provider: dict | None = None,
    queue: dict | None = None,
    current_time: str | None = None,
    bot_version: str | None = None,
) -> str:
    metrics = metrics or {}
    provider = provider or {}
    queue = queue or {}
    return "\n".join(
        [
            "========================",
            "Radar Status",
            "========================",
            "",
            "Scheduler:",
            f"- {_display(scheduler)}",
            "",
            "AI Provider:",
            f"- Provider: {_display(provider.get('provider'))}",
            f"- Model: {_display(provider.get('model'))}",
            "",
            "BOE:",
            f"- Last fetch time: {_display(metrics.get('boe_last_fetch_time'))}",
            f"- Last fetch result: {_display(metrics.get('boe_last_fetch_result'))}",
            "",
            "Candidates:",
            f"- Pending AI: {_display(metrics.get('pending_ai'))}",
            f"- AI completed: {_display(metrics.get('ai_completed'))}",
            f"- Pending review: {_display(metrics.get('pending_review'))}",
            f"- Approved: {_display(metrics.get('approved'))}",
            f"- Published: {_display(metrics.get('published'))}",
            "",
            "AI Queue:",
            f"- Current queue size: {_display(metrics.get('ai_queue_size'))}",
            f"- Batch limit: {_display(queue.get('batch_limit'))}",
            f"- Delay seconds: {_display(queue.get('delay_seconds'))}",
            "",
            "System:",
            f"- Current UTC time: {_display(current_time)}",
            f"- Bot version: {_display(bot_version)}",
        ]
    )


def collect_runtime_status(application=None, metrics: dict | None = None) -> str:
    provider = ai_provider_status()
    queue = ai_queue_status(provider=provider.get("provider"))
    return build_radar_status_text(
        metrics=metrics,
        scheduler=scheduler_status(application),
        provider=provider,
        queue=queue,
        current_time=current_utc_time(),
        bot_version=git_commit_version(),
    )
