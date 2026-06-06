from typing import Protocol


class EmbeddingProviderPort(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the embedding provider identifier."""

    @property
    def model_name(self) -> str:
        """Return the embedding model identifier."""

    @property
    def embedding_dimension(self) -> int | None:
        """Return the known embedding dimension, if available."""

    def embed_text(self, text: str) -> list[float]:
        """Create an embedding for a text fragment."""


EmbeddingProvider = EmbeddingProviderPort
