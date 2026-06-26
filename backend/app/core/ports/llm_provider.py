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
        history: list[tuple[str, str]] | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Generate a response from a language model.

        ``images`` is an optional list of base64-encoded images for vision-capable
        models. ``temperature`` optionally tunes randomness (lower = more precise,
        higher = more creative). ``think`` optionally enables/disables reasoning
        on thinking-capable models. ``history`` is the prior conversation as
        ``(role, content)`` turns ("user"/"assistant"); chat-native providers send
        it as real preceding messages so follow-ups keep context the way ChatGPT or
        Claude do. ``response_format`` optionally constrains the output to a JSON
        Schema/object (see ``core.domain.structured_output``); the bundled
        llama.cpp honours it, other providers may ignore it. Providers that don't
        support a capability ignore it.
        """

    # Streaming is optional: providers that support it expose ``generate_stream``
    # with the same signature, yielding answer-text deltas. Consumers detect it
    # via getattr, so it is intentionally not a required method here.
