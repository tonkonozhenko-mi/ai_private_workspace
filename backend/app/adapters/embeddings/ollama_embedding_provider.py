import httpx


class OllamaEmbeddingProviderError(RuntimeError):
    pass


class OllamaEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: int = 30,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()

    def embed_text(self, text: str) -> list[float]:
        try:
            response = self.client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaEmbeddingProviderError(
                f"Ollama embedding request timed out after {self.timeout_seconds} seconds"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaEmbeddingProviderError(
                f"Unable to reach Ollama embedding API at {self.base_url}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaEmbeddingProviderError(
                "Ollama embedding response was not valid JSON"
            ) from exc

        embedding = payload.get("embedding") if isinstance(payload, dict) else None
        if not isinstance(embedding, list) or not embedding:
            raise OllamaEmbeddingProviderError(
                "Ollama embedding response did not include an embedding"
            )

        try:
            return [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise OllamaEmbeddingProviderError(
                "Ollama embedding response contained invalid vector values"
            ) from exc
