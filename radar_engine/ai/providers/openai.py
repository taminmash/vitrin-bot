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


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAIProvider:
    provider_name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def complete_json(self, messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        if not self.api_key:
            raise AIConfigurationError("OPENAI_API_KEY is not configured")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response_payload = self._post(body)
                content = response_payload["choices"][0]["message"]["content"]
                return parse_json_object(content, "OpenAI")
            except (AIQuotaError, AITimeoutError, AINetworkError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                sleep_before_retry(self.backoff_seconds, attempt)
        raise AINetworkError(f"OpenAI request failed after retries: {last_error}")

    def _post(self, body: bytes) -> dict:
        request = Request(
            OPENAI_CHAT_COMPLETIONS_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "VitrinSpainRadar/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code in {401, 403}:
                raise AIAuthenticationError("OpenAI authentication failed") from error
            if error.code == 429:
                raise AIQuotaError("OpenAI quota or rate limit exceeded") from error
            if error.code == 404:
                raise AIModelUnavailableError(f"OpenAI model is unavailable: {self.model}") from error
            if 500 <= error.code < 600:
                raise AINetworkError(f"OpenAI server error HTTP {error.code}") from error
            raise AIInvalidRequestError(f"OpenAI request failed HTTP {error.code}") from error
        except TimeoutError as error:
            raise AITimeoutError("OpenAI request timed out") from error
        except URLError as error:
            raise AINetworkError(str(error.reason)) from error
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise AIProviderResponseError("OpenAI returned a malformed response") from error

