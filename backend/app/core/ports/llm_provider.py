from typing import Protocol


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        """Generate a response from a language model."""
