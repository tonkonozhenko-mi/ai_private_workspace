from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class StreamingLLMProviderPort(Protocol):
    def generate_stream(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> Iterator[str]:
        """Yield answer text deltas as the model produces them."""


class LLMProviderPort(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the LLM provider identifier."""

    @property
    def model_name(self) -> str | None:
        """Return the LLM model identifier, if available."""

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> str:
        """Generate a response from a language model.

        ``images`` is an optional list of base64-encoded images for vision-capable
        models. ``temperature`` optionally tunes randomness (lower = more precise,
        higher = more creative). ``think`` optionally enables/disables reasoning
        on thinking-capable models. Providers that don't support these ignore them.
        """


LLMProvider = LLMProviderPort
