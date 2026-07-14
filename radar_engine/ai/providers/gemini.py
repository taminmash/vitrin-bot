from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from radar_engine.ai.providers.base import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidRequestError,
    AIModelUnavailableError,
    AINetworkError,
    AIProviderResponseError,
    AIQuotaError,
    AITimeoutError,
    parse_json_object,
    sleep_before_retry,
)


GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_RATE_LIMIT_RETRY_CAP_SECONDS = 20.0


class GeminiProvider:
    provider_name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 1,
        backoff_seconds: float = 0.5,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def complete_json(self, messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        if not self.api_key:
            raise AIConfigurationError("GEMINI_API_KEY is not configured")
        payload = {
            "model": self.model,
            "input": self._messages_to_prompt(messages),
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
            },
        }
        if schema:
            payload["response_format"]["schema"] = schema
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response_payload = self._post(body)
                return parse_json_object(self._extract_output_text(response_payload), "Gemini")
            except AIQuotaError as error:
                last_error = error
                if attempt >= min(self.max_retries, 1):
                    raise
                sleep_before_retry(
                    self.backoff_seconds,
                    attempt,
                    retry_after_seconds=error.retry_after_seconds,
                    max_delay_seconds=GEMINI_RATE_LIMIT_RETRY_CAP_SECONDS,
                )
            except (AITimeoutError, AINetworkError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                sleep_before_retry(self.backoff_seconds, attempt)
        raise AINetworkError(f"Gemini request failed after retries: {last_error}")

    def _post(self, body: bytes) -> dict:
        request = Request(
            GEMINI_INTERACTIONS_URL,
            data=body,
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
                "User-Agent": "VitrinSpainRadar/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            error_body = self._read_error_body(error)
            if error.code in {401, 403}:
                raise AIAuthenticationError("Gemini authentication failed") from error
            if error.code == 429:
                raise AIQuotaError(
                    "Gemini quota or rate limit exceeded",
                    retry_after_seconds=self._retry_after_seconds(error),
                ) from error
            if error.code == 404:
                raise AIModelUnavailableError(f"Gemini model is unavailable: {self.model}") from error
            if 500 <= error.code < 600:
                raise AINetworkError(f"Gemini server error HTTP {error.code}") from error
            if self._looks_like_rate_limit(error_body):
                raise AIQuotaError(
                    "Gemini quota or rate limit exceeded",
                    retry_after_seconds=self._retry_after_seconds(error),
                ) from error
            raise AIInvalidRequestError(f"Gemini request failed HTTP {error.code}") from error
        except TimeoutError as error:
            raise AITimeoutError("Gemini request timed out") from error
        except URLError as error:
            raise AINetworkError(str(error.reason)) from error
        except (json.JSONDecodeError, TypeError) as error:
            raise AIProviderResponseError("Gemini returned a malformed response") from error

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        parts = []
        for message in messages:
            role = (message.get("role") or "user").strip()
            content = (message.get("content") or "").strip()
            if content:
                parts.append(f"{role.upper()}:\n{content}")
        return "\n\n".join(parts)

    def _extract_output_text(self, payload: dict) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text
        text = payload.get("text")
        if isinstance(text, str):
            return text
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
            if texts:
                return "".join(texts)
        raise AIProviderResponseError("Gemini response did not include output text")

    def _read_error_body(self, error: HTTPError) -> str:
        try:
            return error.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _retry_after_seconds(self, error: HTTPError) -> float | None:
        value = error.headers.get("Retry-After") if error.headers else None
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    def _looks_like_rate_limit(self, text: str) -> bool:
        lowered = (text or "").casefold()
        return any(marker in lowered for marker in ("quota", "rate limit", "resource exhausted", "resource_exhausted"))

