from typing import Protocol


class EmbeddingProviderPort(Protocol):
    def embed_text(self, text: str) -> list[float]:
        """Create an embedding for a text fragment."""


EmbeddingProvider = EmbeddingProviderPort
