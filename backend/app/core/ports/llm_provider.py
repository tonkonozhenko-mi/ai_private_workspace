from typing import Protocol


class LLMProviderPort(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the LLM provider identifier."""

    @property
    def model_name(self) -> str | None:
        """Return the LLM model identifier, if available."""

    def generate(self, prompt: str, images: list[str] | None = None) -> str:
        """Generate a response from a language model.

        ``images`` is an optional list of base64-encoded images for vision-capable
        models. Text-only providers ignore it.
        """


LLMProvider = LLMProviderPort
