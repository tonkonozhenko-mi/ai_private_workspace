from collections.abc import Callable

import httpx

from app.adapters.llm.fake_llm_provider import FakeLLMProvider
from app.adapters.llm.llama_server_llm_provider import LlamaServerLLMProvider
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
        llama_server_base_url: str = "http://127.0.0.1:8080",
        llama_server_default_model: str = "local-gguf",
        llama_server_timeout_seconds: int = 120,
        llama_server_client: httpx.Client | None = None,
        default_provider_resolver: Callable[[], str | None] | None = None,
    ) -> None:
        self.default_provider = default_provider.strip().lower()
        # Optional late-bound resolver for the "no provider given" case: lets the
        # container point `create()` at whichever engine is actually live (the active
        # backend) instead of a fixed configured default, so features that don't
        # carry a workspace selection (Investigator, context enrichment, profile
        # suggestions) run on the same engine as everything else. Falls back to
        # `default_provider` when it returns nothing or errors.
        self.default_provider_resolver = default_provider_resolver
        self.ollama_base_url = ollama_base_url
        self.ollama_default_model = ollama_default_model
        self.ollama_timeout_seconds = ollama_timeout_seconds
        self.ollama_client = ollama_client
        self.llama_server_base_url = llama_server_base_url
        self.llama_server_default_model = llama_server_default_model
        self.llama_server_timeout_seconds = llama_server_timeout_seconds
        self.llama_server_client = llama_server_client

    def supports(self, provider: str) -> bool:
        return provider.strip().lower() in {"fake", "ollama", "llamacpp"}

    def _resolved_default_provider(self) -> str:
        """The provider to use when a caller passes none: the live active backend
        (via the resolver) if it names a supported engine, otherwise the static
        configured default. Best-effort — a failing resolver never breaks create()."""
        if self.default_provider_resolver is not None:
            try:
                resolved = self.default_provider_resolver()
            except Exception:  # noqa: BLE001 - fall back to the configured default
                resolved = None
            if resolved and resolved.strip().lower() in {"fake", "ollama", "llamacpp"}:
                return resolved.strip().lower()
        return self.default_provider

    def create(
        self,
        provider: str | None = None,
        model: str | None = None,
    ) -> LLMProviderPort:
        provider_name = (provider or self._resolved_default_provider()).strip().lower()
        model_name = model.strip() if model and model.strip() else None

        if provider_name == "fake":
            return FakeLLMProvider(model_name=model_name or "fake-llm")
        if provider_name == "ollama":
            if self.ollama_client is None:
                self.ollama_client = httpx.Client()
            return OllamaLLMProvider(
                base_url=self.ollama_base_url,
                model=model_name or self.ollama_default_model,
                timeout_seconds=self.ollama_timeout_seconds,
                client=self.ollama_client,
            )
        if provider_name == "llamacpp":
            if self.llama_server_client is None:
                self.llama_server_client = httpx.Client()
            return LlamaServerLLMProvider(
                base_url=self.llama_server_base_url,
                model=model_name or self.llama_server_default_model,
                timeout_seconds=self.llama_server_timeout_seconds,
                client=self.llama_server_client,
            )

        raise LLMProviderFactoryError(f"Unsupported LLM provider: {provider_name}")
