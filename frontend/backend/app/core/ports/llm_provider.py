from typing import Protocol


class LLMProviderPort(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the LLM provider identifier."""

    @property
    def model_name(self) -> str | None:
        """Return the LLM model identifier, if available."""

    def generate(self, prompt: str) -> str:
        """Generate a response from a language model."""


LLMProvider = LLMProviderPort
