import httpx
from time import sleep


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

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
    ) -> str:
        response = self._request_with_one_local_retry(prompt, images, temperature)

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

    def _request_with_one_local_retry(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
    ) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            # Ollama accepts base64-encoded images for vision-capable models.
            payload["images"] = images
        if temperature is not None:
            # Ollama generation tuning goes under "options".
            payload["options"] = {"temperature": temperature}
        for attempt in range(2):
            try:
                response = self.client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text.strip()[:300]
                if exc.response.status_code == 404:
                    raise OllamaLLMProviderError(
                        f"Ollama model '{self.model}' is not installed at {self.base_url}. "
                        f"Refresh Installed Models or download it first. {detail}"
                    ) from exc
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc

            if attempt == 0:
                sleep(0.25)

        if isinstance(last_error, httpx.TimeoutException):
            raise OllamaLLMProviderError(
                f"Ollama LLM request timed out after {self.timeout_seconds} seconds. "
                f"The app retried model '{self.model}' once; the model may still be loading."
            ) from last_error
        raise OllamaLLMProviderError(
            f"Unable to reach Ollama generation API at {self.base_url}. "
            f"The app retried model '{self.model}' once."
        ) from last_error
