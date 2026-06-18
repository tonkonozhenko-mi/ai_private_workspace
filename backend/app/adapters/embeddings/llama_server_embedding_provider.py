"""Embeddings via a local ``llama-server`` started with ``--embedding``.

One ``llama-server`` process serves one model, so embeddings run on their own
instance/port, separate from the answer model — the same shape Ollama uses
internally. Uses the OpenAI-compatible ``/v1/embeddings`` endpoint.
"""

import time

import httpx

# The embedding server can briefly return 5xx (or refuse a connection) while it
# warms up after /health goes green, or when its single slot is momentarily busy
# during a burst of indexing requests. Those are transient, so we retry a few
# times with a short backoff instead of failing the whole "Build context" step.
_RETRY_ATTEMPTS = 4
_RETRY_BASE_DELAY_SECONDS = 0.5


class LlamaServerEmbeddingProviderError(RuntimeError):
    pass


class LlamaServerEmbeddingProvider:
    provider_name = "llamacpp"

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
        response: httpx.Response | None = None
        last_detail = ""
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                candidate = self.client.post(
                    f"{self.base_url}/v1/embeddings",
                    json={"model": self.model, "input": text},
                    timeout=self.timeout_seconds,
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_detail = str(exc)
            else:
                if candidate.status_code < 500:
                    try:
                        candidate.raise_for_status()
                    except httpx.HTTPError as exc:
                        raise LlamaServerEmbeddingProviderError(
                            f"Unable to reach llama-server embedding API at "
                            f"{self.base_url}: {exc}"
                        ) from exc
                    response = candidate
                    break
                last_detail = f"HTTP {candidate.status_code}"
            if attempt < _RETRY_ATTEMPTS - 1:
                time.sleep(min(2.0, _RETRY_BASE_DELAY_SECONDS * (2**attempt)))

        if response is None:
            raise LlamaServerEmbeddingProviderError(
                f"llama-server embedding API at {self.base_url} did not respond "
                f"successfully after {_RETRY_ATTEMPTS} attempts: {last_detail}"
            )

        try:
            payload = response.json()
            embedding = payload["data"][0]["embedding"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlamaServerEmbeddingProviderError(
                "llama-server embedding response did not include an embedding"
            ) from exc

        if not isinstance(embedding, list) or not embedding:
            raise LlamaServerEmbeddingProviderError(
                "llama-server returned an empty embedding"
            )

        try:
            vector = [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise LlamaServerEmbeddingProviderError(
                "llama-server embedding contained invalid vector values"
            ) from exc

        self._embedding_dimension = len(vector)
        return vector
