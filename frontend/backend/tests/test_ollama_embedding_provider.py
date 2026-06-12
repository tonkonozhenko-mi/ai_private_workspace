import json
import os

import httpx
import pytest

from app.adapters.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from app.adapters.embeddings.ollama_embedding_provider import (
    OllamaEmbeddingProvider,
    OllamaEmbeddingProviderError,
)
from app.api.dependencies import build_embedding_provider
from app.config.settings import get_settings


RUN_OLLAMA_TESTS = os.getenv("RUN_OLLAMA_TESTS", "").lower() == "true"


def test_ollama_embedding_provider_returns_embedding() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ollama.test/api/embeddings"
        assert json.loads(request.content) == {
            "model": "nomic-embed-text",
            "prompt": "hello workspace",
        }
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    provider = _provider(handler)

    embedding = provider.embed_text("hello workspace")

    assert embedding == [0.1, 0.2, 0.3]
    assert provider.provider_name == "ollama"
    assert provider.model_name == "nomic-embed-text"
    assert provider.embedding_dimension == 3


def test_ollama_embedding_provider_missing_embedding_raises_clear_error() -> None:
    provider = _provider(
        lambda request: httpx.Response(200, json={"model": "nomic-embed-text"})
    )

    with pytest.raises(
        OllamaEmbeddingProviderError,
        match="Ollama embedding response did not include an embedding",
    ):
        provider.embed_text("hello workspace")


def test_ollama_embedding_provider_unreachable_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler)

    with pytest.raises(
        OllamaEmbeddingProviderError,
        match="Unable to reach Ollama embedding API at http://ollama.test",
    ):
        provider.embed_text("hello workspace")


def test_ollama_embedding_provider_timeout_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = _provider(handler, timeout_seconds=7)

    with pytest.raises(
        OllamaEmbeddingProviderError,
        match="Ollama embedding request timed out after 7 seconds",
    ):
        provider.embed_text("hello workspace")


def test_build_embedding_provider_uses_fake_by_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    get_settings.cache_clear()

    provider = build_embedding_provider()

    assert isinstance(provider, FakeEmbeddingProvider)
    assert provider.provider_name == "fake"
    assert provider.model_name == "fake-embedding"
    assert provider.embedding_dimension == 128
    get_settings.cache_clear()


def test_build_embedding_provider_can_enable_ollama(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "test-embed-model")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "9")
    get_settings.cache_clear()

    provider = build_embedding_provider()

    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.base_url == "http://ollama.test"
    assert provider.model == "test-embed-model"
    assert provider.timeout_seconds == 9
    provider.client.close()
    get_settings.cache_clear()


@pytest.mark.skipif(
    not RUN_OLLAMA_TESTS,
    reason="Set RUN_OLLAMA_TESTS=true to run Ollama integration tests.",
)
def test_ollama_embedding_provider_integration() -> None:
    provider = OllamaEmbeddingProvider(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30")),
    )

    try:
        embedding = provider.embed_text("Private Project AI Workbench")
    finally:
        provider.client.close()

    assert embedding
    assert all(isinstance(value, float) for value in embedding)


def _provider(
    handler,
    timeout_seconds: int = 30,
) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url="http://ollama.test",
        model="nomic-embed-text",
        timeout_seconds=timeout_seconds,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
