import httpx

from app.core.domain.runtime_health import RuntimeComponentHealth


class OllamaRuntimeHealthChecker:
    def __init__(
        self,
        embedding_provider: str,
        llm_provider: str,
        base_url: str,
        embedding_model: str,
        llm_model: str,
        timeout_seconds: float = 3,
        client: httpx.Client | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider.lower()
        self.llm_provider = llm_provider.lower()
        self.base_url = base_url.rstrip("/")
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()

    def check(self) -> RuntimeComponentHealth:
        required_models = self._required_models()
        if not required_models:
            return RuntimeComponentHealth(
                name="ollama",
                configured=False,
                healthy=True,
                status="not_configured",
                details="Ollama is not selected for embeddings or LLM generation.",
            )

        try:
            response = self.client.get(
                f"{self.base_url}/api/tags",
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return RuntimeComponentHealth(
                name="ollama",
                configured=True,
                healthy=False,
                status="unreachable",
                details=f"Ollama is unreachable at {self.base_url}: {exc}",
            )
        except httpx.HTTPError as exc:
            return RuntimeComponentHealth(
                name="ollama",
                configured=True,
                healthy=False,
                status="error",
                details=f"Ollama health request failed at {self.base_url}: {exc}",
            )

        try:
            payload = response.json()
            installed_models = self._installed_models(payload)
        except (TypeError, ValueError) as exc:
            return RuntimeComponentHealth(
                name="ollama",
                configured=True,
                healthy=False,
                status="error",
                details=f"Ollama returned an invalid model list: {exc}",
            )

        missing_models = [
            model
            for model in required_models
            if not self._model_is_installed(model, installed_models)
        ]
        if missing_models:
            return RuntimeComponentHealth(
                name="ollama",
                configured=True,
                healthy=False,
                status="error",
                details=f"Configured Ollama models are missing: {', '.join(missing_models)}.",
            )

        return RuntimeComponentHealth(
            name="ollama",
            configured=True,
            healthy=True,
            status="ok",
            details=(
                f"Ollama is reachable and configured models are available: "
                f"{', '.join(required_models)}."
            ),
        )

    def _required_models(self) -> list[str]:
        models: list[str] = []
        if self.embedding_provider == "ollama":
            models.append(self.embedding_model)
        if self.llm_provider == "ollama" and self.llm_model not in models:
            models.append(self.llm_model)
        return models

    @staticmethod
    def _installed_models(payload) -> set[str]:
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise ValueError("response did not include a models list")

        installed_models: set[str] = set()
        for model in payload["models"]:
            if not isinstance(model, dict):
                continue
            for key in ("name", "model"):
                value = model.get(key)
                if isinstance(value, str):
                    installed_models.add(value)
        return installed_models

    @staticmethod
    def _model_is_installed(required_model: str, installed_models: set[str]) -> bool:
        return any(
            installed_model == required_model
            or installed_model.removesuffix(":latest") == required_model
            or required_model.removesuffix(":latest") == installed_model
            for installed_model in installed_models
        )
