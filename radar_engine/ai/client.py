from __future__ import annotations

import os

from radar_engine.ai.providers import (
    AIConfigurationError,
    GeminiProvider,
    JSONAIProvider,
    OpenAIProvider,
    ProviderInfo,
)


DEFAULT_AI_PROVIDER = "gemini"
ALLOWED_AI_PROVIDERS = {"gemini", "openai"}


def selected_ai_provider(value: str | None = None) -> str:
    raw = os.getenv("AI_PROVIDER") if value is None else value
    provider = (raw or DEFAULT_AI_PROVIDER).strip().casefold()
    if provider not in ALLOWED_AI_PROVIDERS:
        raise AIConfigurationError(
            f"Invalid AI_PROVIDER={raw!r}; expected one of: {', '.join(sorted(ALLOWED_AI_PROVIDERS))}"
        )
    return provider


def build_ai_provider(provider_name: str | None = None) -> JSONAIProvider:
    provider = selected_ai_provider(provider_name)
    if provider == "gemini":
        return GeminiProvider()
    if provider == "openai":
        return OpenAIProvider()
    raise AIConfigurationError(f"Unsupported AI provider: {provider}")


def provider_info(provider_name: str | None = None) -> ProviderInfo:
    provider = build_ai_provider(provider_name)
    api_key = getattr(provider, "api_key", None)
    return ProviderInfo(provider=getattr(provider, "provider_name", ""), model=provider.model, configured=bool(api_key))


class OpenAIClient(OpenAIProvider):
    """Backward-compatible alias for tests and explicit OpenAI use."""


class AIClient:
    """Default provider facade used by summarization and classification."""

    def __init__(self, provider: JSONAIProvider | None = None):
        self.provider = provider or build_ai_provider()

    @property
    def model(self) -> str:
        return self.provider.model

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "provider_name", selected_ai_provider())

    def complete_json(self, messages: list[dict[str, str]], schema: dict | None = None) -> dict:
        return self.provider.complete_json(messages, schema=schema)
