"""Batch embedding: provider batch API + the index use case's batched embed."""

from app.core.use_cases.index_workspace import IndexWorkspaceUseCase


class _BatchEmbed:
    """Provider that supports batch embedding and records call sizes."""

    provider_name = "fake"
    model_name = "fake"
    embedding_dimension = 2

    def __init__(self):
        self.batch_calls: list[int] = []

    def embed_text(self, text):
        return [float(len(text)), 1.0]

    def embed_texts(self, texts):
        self.batch_calls.append(len(texts))
        return [self.embed_text(t) for t in texts]


class _SingleEmbed:
    """Provider with no batch API — forces the per-text fallback."""

    provider_name = "fake"
    model_name = "fake"
    embedding_dimension = 2

    def __init__(self):
        self.single_calls = 0

    def embed_text(self, text):
        self.single_calls += 1
        return [float(len(text)), 1.0]


def _uc(embed):
    # Only the embedding provider is exercised by _embed_texts.
    return IndexWorkspaceUseCase(
        workspace_repository=None,
        project_scan_repository=None,
        file_system=None,
        embedding_provider=embed,
        vector_store=None,
        index_status_repository=None,
    )


def test_embed_texts_uses_batch_in_chunks_preserving_order():
    embed = _BatchEmbed()
    uc = _uc(embed)
    texts = [f"t{i}" for i in range(150)]  # > one batch of 64
    out = uc._embed_texts(texts)
    assert len(out) == 150
    # Batched in groups of 64 → 64, 64, 22.
    assert embed.batch_calls == [64, 64, 22]
    # Order preserved (vector encodes text length; all "tNN" same-ish, check first/last identity).
    assert out[0] == embed.embed_text("t0")
    assert out[-1] == embed.embed_text("t149")


def test_embed_texts_falls_back_to_single():
    embed = _SingleEmbed()
    out = _uc(embed)._embed_texts(["a", "bb", "ccc"])
    assert embed.single_calls == 3
    assert len(out) == 3


def test_llama_embed_texts_parses_multiple_vectors():
    from app.adapters.embeddings.llama_server_embedding_provider import (
        LlamaServerEmbeddingProvider,
    )

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

    class _Client:
        def __init__(self):
            self.inputs = None

        def post(self, url, json, timeout):
            self.inputs = json["input"]
            return _Resp()

    client = _Client()
    provider = LlamaServerEmbeddingProvider("http://test", "m", client=client)
    vectors = provider.embed_texts(["one", "two"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert client.inputs == ["one", "two"]  # one request, both inputs
    assert provider.embedding_dimension == 2


def test_llama_embed_text_uses_request():
    from app.adapters.embeddings.llama_server_embedding_provider import (
        LlamaServerEmbeddingProvider,
    )

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [1.0, 2.0, 3.0]}]}

    class _Client:
        def post(self, *a, **k):
            return _Resp()

    provider = LlamaServerEmbeddingProvider("http://test", "m", client=_Client())
    assert provider.embed_text("hi") == [1.0, 2.0, 3.0]
