from __future__ import annotations

import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 30,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def complete_json(self, messages: list[dict[str, str]]) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                request = Request(
                    OPENAI_CHAT_COMPLETIONS_URL,
                    data=body,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                content = response_payload["choices"][0]["message"]["content"]
                if not content:
                    raise ValueError("OpenAI response content is empty")
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("OpenAI response JSON must be an object")
                return parsed
            except (OSError, URLError, TimeoutError) as error:
                last_error = error
                if attempt >= self.max_retries:
                    break
                time.sleep(self.backoff_seconds * (2**attempt))
            except (KeyError, IndexError, json.JSONDecodeError, ValueError):
                raise
        raise RuntimeError(f"OpenAI request failed after retries: {last_error}")
