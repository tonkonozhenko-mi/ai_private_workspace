import httpx


class OllamaLLMProviderError(RuntimeError):
    pass


class OllamaLLMProvider:
    provider_name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: int = 120,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaLLMProviderError(
                f"Ollama LLM request timed out after {self.timeout_seconds} seconds"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaLLMProviderError(
                f"Unable to reach Ollama generation API at {self.base_url}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaLLMProviderError(
                "Ollama generation response was not valid JSON"
            ) from exc

        generated_text = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(generated_text, str) or not generated_text.strip():
            raise OllamaLLMProviderError(
                "Ollama generation response did not include response text"
            )

        return generated_text
