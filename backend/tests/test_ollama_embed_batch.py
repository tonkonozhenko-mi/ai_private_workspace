"""Ollama batch embedding: one /api/embed call, with per-text fallback."""

from app.adapters.embeddings.ollama_embedding_provider import (
    OllamaEmbeddingProvider,
    OllamaEmbeddingProviderError,  # noqa: F401 (imported for completeness)
)


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("error", response=self)

    def json(self):
        return self._payload


class _RecordingClient:
    """Returns a queued response per POST and records the paths hit."""

    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        return self.responder(url, json)


def test_batch_uses_single_embed_call():
    def responder(url, body):
        assert url.endswith("/api/embed")
        return _Response({"embeddings": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]})

    client = _RecordingClient(responder)
    provider = OllamaEmbeddingProvider("http://x:11434", "nomic", client=client)
    vectors = provider.embed_texts(["a", "b", "c"])

    assert vectors == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
    assert provider.embedding_dimension == 2
    assert len(client.calls) == 1  # ONE request for the whole batch
    assert client.calls[0][1]["input"] == ["a", "b", "c"]


def test_falls_back_to_per_text_on_404():
    def responder(url, body):
        if url.endswith("/api/embed"):
            return _Response({}, status_code=404)  # old Ollama: no batch endpoint
        assert url.endswith("/api/embeddings")
        return _Response({"embedding": [0.5, 0.5]})

    client = _RecordingClient(responder)
    provider = OllamaEmbeddingProvider("http://x:11434", "nomic", client=client)
    vectors = provider.embed_texts(["a", "b"])

    assert vectors == [[0.5, 0.5], [0.5, 0.5]]
    # 1 failed batch attempt + 2 per-text calls
    assert sum(1 for url, _ in client.calls if url.endswith("/api/embeddings")) == 2


def test_shape_mismatch_falls_back():
    def responder(url, body):
        if url.endswith("/api/embed"):
            return _Response({"embeddings": [[1.0, 2.0]]})  # only 1 for 2 inputs
        return _Response({"embedding": [9.0]})

    client = _RecordingClient(responder)
    provider = OllamaEmbeddingProvider("http://x:11434", "nomic", client=client)
    vectors = provider.embed_texts(["a", "b"])
    assert vectors == [[9.0], [9.0]]


def test_empty_input_returns_empty():
    client = _RecordingClient(lambda url, body: _Response({}))
    provider = OllamaEmbeddingProvider("http://x:11434", "nomic", client=client)
    assert provider.embed_texts([]) == []
    assert client.calls == []
