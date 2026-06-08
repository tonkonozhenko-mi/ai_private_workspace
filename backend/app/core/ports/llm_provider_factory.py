from typing import Protocol

from app.core.ports.llm_provider import LLMProviderPort


class LLMProviderFactoryError(ValueError):
    pass


class LLMProviderFactoryPort(Protocol):
    def supports(self, provider: str) -> bool:
        """Return whether a provider can be selected per request."""

    def create(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> LLMProviderPort:
        """Create the configured default or a supported per-request LLM provider."""
