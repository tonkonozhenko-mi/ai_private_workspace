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

    # Batch embedding is optional: providers that can embed several texts in one
    # request expose ``embed_texts(texts) -> list[list[float]]`` (vectors in the
    # same order). Consumers detect it via ``getattr`` and fall back to per-text
    # ``embed_text`` when it's absent, so it is intentionally not required here.


EmbeddingProvider = EmbeddingProviderPort
