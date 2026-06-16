import json
import os

import httpx
import pytest

from app.adapters.llm.fake_llm_provider import FakeLLMProvider
from app.adapters.llm.ollama_llm_provider import (
    OllamaLLMProvider,
    OllamaLLMProviderError,
)
from app.api.dependencies import build_llm_provider
from app.config.settings import get_settings

RUN_OLLAMA_TESTS = os.getenv("RUN_OLLAMA_TESTS", "").lower() == "true"


def test_ollama_llm_provider_returns_generated_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ollama.test/api/generate"
        assert json.loads(request.content) == {
            "model": "llama3.2",
            "prompt": "Explain the workspace.",
            "stream": False,
        }
        return httpx.Response(200, json={"response": "The workspace uses local RAG."})

    provider = _provider(handler)

    result = provider.generate("Explain the workspace.")

    assert result == "The workspace uses local RAG."
    assert provider.provider_name == "ollama"
    assert provider.model_name == "llama3.2"


def test_ollama_llm_provider_missing_response_raises_clear_error() -> None:
    provider = _provider(lambda request: httpx.Response(200, json={"model": "llama3.2"}))

    with pytest.raises(
        OllamaLLMProviderError,
        match="Ollama generation response did not include response text",
    ):
        provider.generate("Explain the workspace.")


def test_ollama_llm_provider_unreachable_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler)

    with pytest.raises(
        OllamaLLMProviderError,
        match="Unable to reach Ollama generation API at http://ollama.test",
    ):
        provider.generate("Explain the workspace.")


def test_ollama_llm_provider_timeout_raises_clear_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = _provider(handler, timeout_seconds=17)

    with pytest.raises(
        OllamaLLMProviderError,
        match="Ollama LLM request timed out after 17 seconds",
    ):
        provider.generate("Explain the workspace.")


def test_build_llm_provider_uses_fake_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    get_settings.cache_clear()

    provider = build_llm_provider()

    assert isinstance(provider, FakeLLMProvider)
    assert provider.provider_name == "fake"
    assert provider.model_name == "fake-llm"
    get_settings.cache_clear()


def test_build_llm_provider_can_enable_ollama(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_LLM_MODEL", "test-llm-model")
    monkeypatch.setenv("OLLAMA_LLM_TIMEOUT_SECONDS", "19")
    get_settings.cache_clear()

    provider = build_llm_provider()

    assert isinstance(provider, OllamaLLMProvider)
    assert provider.base_url == "http://ollama.test"
    assert provider.model_name == "test-llm-model"
    assert provider.timeout_seconds == 19
    provider.client.close()
    get_settings.cache_clear()


@pytest.mark.skipif(
    not RUN_OLLAMA_TESTS,
    reason="Set RUN_OLLAMA_TESTS=true to run Ollama integration tests.",
)
def test_ollama_llm_provider_integration() -> None:
    provider = OllamaLLMProvider(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_LLM_MODEL", "llama3.2"),
        timeout_seconds=int(os.getenv("OLLAMA_LLM_TIMEOUT_SECONDS", "120")),
    )

    try:
        response = provider.generate("Reply with a short sentence confirming local generation.")
    finally:
        provider.client.close()

    assert response.strip()


def _provider(
    handler,
    timeout_seconds: int = 120,
) -> OllamaLLMProvider:
    return OllamaLLMProvider(
        base_url="http://ollama.test",
        model="llama3.2",
        timeout_seconds=timeout_seconds,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
