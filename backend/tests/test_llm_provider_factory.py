import pytest

from app.adapters.llm.fake_llm_provider import FakeLLMProvider
from app.adapters.llm.llm_provider_factory import LLMProviderFactory
from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider
from app.core.ports.llm_provider_factory import LLMProviderFactoryError


def test_factory_default_returns_configured_fake_provider() -> None:
    factory = _factory(default_provider="fake")

    provider = factory.create()

    assert isinstance(provider, FakeLLMProvider)
    assert provider.provider_name == "fake"
    assert provider.model_name == "fake-llm"


def test_factory_creates_fake_provider_with_model_override() -> None:
    factory = _factory(default_provider="ollama")

    provider = factory.create(provider="fake", model="fake-llm-alt")

    assert isinstance(provider, FakeLLMProvider)
    assert provider.provider_name == "fake"
    assert provider.model_name == "fake-llm-alt"


def test_factory_creates_ollama_provider_with_model_override_without_calling() -> None:
    factory = _factory(default_provider="fake")

    provider = factory.create(provider="ollama", model="qwen2.5-coder")

    assert isinstance(provider, OllamaLLMProvider)
    assert provider.provider_name == "ollama"
    assert provider.model_name == "qwen2.5-coder"
    assert provider.base_url == "http://ollama.test"
    assert provider.timeout_seconds == 17
    provider.client.close()


def test_factory_uses_configured_ollama_model_without_override() -> None:
    factory = _factory(default_provider="ollama")

    provider = factory.create()

    assert isinstance(provider, OllamaLLMProvider)
    assert provider.model_name == "llama3.2"
    provider.client.close()


def test_factory_reuses_ollama_http_client_for_overrides() -> None:
    factory = _factory(default_provider="fake")

    first = factory.create(provider="ollama", model="llama3.2")
    second = factory.create(provider="ollama", model="qwen2.5-coder")

    assert isinstance(first, OllamaLLMProvider)
    assert isinstance(second, OllamaLLMProvider)
    assert first.client is second.client
    first.client.close()


def test_factory_rejects_unsupported_provider() -> None:
    factory = _factory(default_provider="fake")

    with pytest.raises(
        LLMProviderFactoryError,
        match="Unsupported LLM provider: custom",
    ):
        factory.create(provider="custom", model="private-model")


def test_factory_reports_supported_override_providers_without_creating_them() -> None:
    factory = _factory(default_provider="fake")

    assert factory.supports("fake") is True
    assert factory.supports(" OLLAMA ") is True
    assert factory.supports("custom") is False
    assert factory.ollama_client is None


def _factory(default_provider: str) -> LLMProviderFactory:
    return LLMProviderFactory(
        default_provider=default_provider,
        ollama_base_url="http://ollama.test",
        ollama_default_model="llama3.2",
        ollama_timeout_seconds=17,
    )
