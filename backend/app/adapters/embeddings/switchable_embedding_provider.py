"""An embedding provider whose backend can be switched at runtime.

Embeddings are an app-wide singleton (the same vectorizer must index and search),
but the user can choose Ollama or llama.cpp. This wrapper holds the active
delegate and lets the model-setup flow swap it — e.g. to llama.cpp once its
engine is running — without restarting the backend.

Switching changes which engine produces *new* vectors. The setup flow chooses
the backend before building the index, so indexing and later search stay
consistent. Switching after an index exists implies a context rebuild.
"""

from app.core.ports.embedding_provider import EmbeddingProviderPort


class SwitchableEmbeddingProvider:
    def __init__(self, delegate: EmbeddingProviderPort) -> None:
        self._delegate = delegate

    def set_delegate(self, delegate: EmbeddingProviderPort) -> None:
        self._delegate = delegate

    @property
    def active_provider(self) -> str:
        return self._delegate.provider_name

    @property
    def provider_name(self) -> str:
        return self._delegate.provider_name

    @property
    def model_name(self) -> str:
        return self._delegate.model_name

    @property
    def embedding_dimension(self) -> int | None:
        return self._delegate.embedding_dimension

    def embed_text(self, text: str) -> list[float]:
        return self._delegate.embed_text(text)
