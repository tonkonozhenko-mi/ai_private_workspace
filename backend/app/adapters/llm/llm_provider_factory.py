import httpx

from app.adapters.llm.fake_llm_provider import FakeLLMProvider
from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import LLMProviderFactoryError


class LLMProviderFactory:
    def __init__(
        self,
        default_provider: str,
        ollama_base_url: str,
        ollama_default_model: str,
        ollama_timeout_seconds: int = 120,
        ollama_client: httpx.Client | None = None,
    ) -> None:
        self.default_provider = default_provider.strip().lower()
        self.ollama_base_url = ollama_base_url
        self.ollama_default_model = ollama_default_model
        self.ollama_timeout_seconds = ollama_timeout_seconds
        self.ollama_client = ollama_client

    def create(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> LLMProviderPort:
        provider_name = (provider or self.default_provider).strip().lower()
        model_name = model.strip() if model and model.strip() else None

        if provider_name == "fake":
            return FakeLLMProvider()
        if provider_name == "ollama":
            if self.ollama_client is None:
                self.ollama_client = httpx.Client()
            return OllamaLLMProvider(
                base_url=self.ollama_base_url,
                model=model_name or self.ollama_default_model,
                timeout_seconds=self.ollama_timeout_seconds,
                client=self.ollama_client,
            )

        raise LLMProviderFactoryError(f"Unsupported LLM provider: {provider_name}")
