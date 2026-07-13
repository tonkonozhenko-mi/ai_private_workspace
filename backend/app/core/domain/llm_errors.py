"""Errors an LLM engine can raise that the app must *understand*, not just report.

Most engine failures are alike: the process died, the port is closed, the model
isn't installed. One is different — the prompt was longer than the model's memory.
That one is our fault, not the engine's, and it has a remedy: send less context
and ask again. It therefore gets its own type, defined in the core so use cases
can catch it without importing an adapter.
"""


class ContextOverflowError(RuntimeError):
    """The prompt exceeded the model's context window.

    ``prompt_tokens`` and ``context_window`` are what the engine reported, so the
    message we eventually show the person can be specific rather than a guess.
    """

    def __init__(
        self,
        message: str,
        *,
        prompt_tokens: int | None = None,
        context_window: int | None = None,
    ) -> None:
        super().__init__(message)
        self.prompt_tokens = prompt_tokens
        self.context_window = context_window

    @property
    def overflow_ratio(self) -> float:
        """How much smaller the prompt must get, with 10% to spare.

        Falls back to a half-sized retry when the engine gave no numbers.
        """
        if not self.prompt_tokens or not self.context_window:
            return 0.5
        if self.prompt_tokens <= 0:
            return 0.5
        return max(0.1, min(0.9, (self.context_window / self.prompt_tokens) * 0.9))


def context_overflow_answer(error: ContextOverflowError) -> str:
    """What to say when even the retry didn't fit.

    Not "check that the engine is running" — the engine is running, and answered
    us precisely. Say what was too big, say we already tried the obvious remedy,
    and name the two things the person can actually do.
    """
    if error.prompt_tokens and error.context_window:
        size = (
            f" ({error.prompt_tokens:,} tokens against this model's "
            f"{error.context_window:,}-token window)"
        )
    else:
        size = ""
    return (
        f"The question and its context were too large for this model's memory{size}. "
        "I retried with less context and it still did not fit. "
        "Try a shorter question, or a model with a larger context window."
    )
