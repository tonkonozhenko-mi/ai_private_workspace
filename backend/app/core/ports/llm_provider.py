from typing import Protocol


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

    # Streaming is optional: providers that support it expose ``generate_stream``
    # with the same signature, yielding answer-text deltas. Consumers detect it
    # via getattr, so it is intentionally not a required method here.
