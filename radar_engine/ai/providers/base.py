from __future__ import annotations

from dataclasses import dataclass
import json
import random
import re
import time
from typing import Protocol


class AIProviderError(RuntimeError):
    retryable = False


class AIConfigurationError(AIProviderError):
    pass


class AIAuthenticationError(AIProviderError):
    pass


class AIQuotaError(AIProviderError):
    retryable = True


class AITimeoutError(AIProviderError):
    retryable = True


class AINetworkError(AIProviderError):
    retryable = True


class AIProviderResponseError(AIProviderError, ValueError):
    pass


class AIModelUnavailableError(AIProviderError):
    pass


class AIInvalidRequestError(AIProviderError):
    pass


class JSONAIProvider(Protocol):
    model: str
    provider_name: str

    def complete_json(self, messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        ...


@dataclass(frozen=True)
class ProviderInfo:
    provider: str
    model: str
    configured: bool


def parse_json_object(text: str, provider_name: str) -> dict:
    cleaned = (text or "").strip()
    if not cleaned:
        raise AIProviderResponseError(f"{provider_name} response text is empty")
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise AIProviderResponseError(f"{provider_name} response is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise AIProviderResponseError(f"{provider_name} response JSON must be an object")
    return parsed


def sleep_before_retry(base_seconds: float, attempt: int) -> None:
    delay = max(0.0, base_seconds) * (2**attempt)
    if delay:
        delay += random.uniform(0, min(0.25, delay))
    time.sleep(delay)
