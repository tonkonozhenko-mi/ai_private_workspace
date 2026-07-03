import httpx


class OllamaEmbeddingProviderError(RuntimeError):
    pass


class OllamaEmbeddingProvider:
    provider_name = "ollama"

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
        self._embedding_dimension: int | None = None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def embedding_dimension(self) -> int | None:
        return self._embedding_dimension

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
            vector = [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise OllamaEmbeddingProviderError(
                "Ollama embedding response contained invalid vector values"
            ) from exc

        self._embedding_dimension = len(vector)
        return vector

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed several texts in ONE request via Ollama's ``/api/embed`` (array
        input), instead of N sequential ``/api/embeddings`` calls — a big speed-up
        for indexing. Falls back to per-text embedding on older Ollama builds that
        don't have ``/api/embed`` (HTTP 404) or return an unexpected shape, so it
        works across versions. Vector order matches the input order.
        """
        if not texts:
            return []
        try:
            response = self.client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": list(texts)},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaEmbeddingProviderError(
                f"Ollama embedding request timed out after {self.timeout_seconds} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            # Endpoint missing on older Ollama → embed one at a time instead.
            if exc.response is not None and exc.response.status_code == 404:
                return [self.embed_text(text) for text in texts]
            raise OllamaEmbeddingProviderError(
                f"Unable to reach Ollama embedding API at {self.base_url}"
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

        embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            # Unexpected shape (or a build that ignores array input) → be safe.
            return [self.embed_text(text) for text in texts]

        vectors: list[list[float]] = []
        for embedding in embeddings:
            if not isinstance(embedding, list) or not embedding:
                raise OllamaEmbeddingProviderError(
                    "Ollama batch embedding response contained an empty vector"
                )
            try:
                vectors.append([float(value) for value in embedding])
            except (TypeError, ValueError) as exc:
                raise OllamaEmbeddingProviderError(
                    "Ollama embedding response contained invalid vector values"
                ) from exc

        self._embedding_dimension = len(vectors[0])
        return vectors
