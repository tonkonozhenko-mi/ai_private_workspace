from typing import Protocol

from app.core.ports.llm_provider import LLMProviderPort


class LLMProviderFactoryError(ValueError):
    pass


class LLMProviderFactoryPort(Protocol):
    def create(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> LLMProviderPort:
        """Create the configured default or a supported per-request LLM provider."""
