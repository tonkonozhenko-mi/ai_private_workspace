import json
from collections.abc import Iterator
from time import sleep

import httpx

from app.core.domain.rag_prompt import render_conversation_history
from app.core.domain.structured_output import ollama_format_from_response_format


class OllamaLLMProviderError(RuntimeError):
    pass


def _with_history(prompt: str, history: list[tuple[str, str]] | None) -> str:
    """Prepend recent dialogue to the prompt.

    Ollama's ``/api/generate`` is prompt-only (no message array), so to give it
    the same follow-up memory llama.cpp gets from real chat messages, we render
    the prior turns as a short text preface.
    """
    section = render_conversation_history(history)
    return f"{section}{prompt}" if section else prompt


def _coerce_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _is_thinking_unsupported(response: "httpx.Response") -> bool:
    """True when Ollama rejected a request because the model can't think.

    Models without reasoning support return HTTP 400 with a body like
    "<model> does not support thinking". We detect that so the caller can
    transparently retry without the ``think`` flag.
    """
    if response.status_code != 400:
        return False
    try:
        body = response.text.lower()
    except Exception:
        return False
    return "think" in body


class OllamaLLMProvider:
    provider_name = "ollama"
    # Ollama constrains output via a top-level ``format`` (raw JSON Schema). We
    # translate the OpenAI-style ``response_format`` to it, so structured/agent
    # callers get the same schema-constrained JSON they get on llama.cpp. Older
    # Ollama builds that reject a schema ``format`` degrade gracefully (see the
    # 400 fallback in ``_request_with_one_local_retry``).
    supports_structured_output = True

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: int = 120,
        client: httpx.Client | None = None,
        context_window: int = 4096,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()
        # We pin Ollama's per-request window via ``num_ctx`` (see _options) so the
        # window we report is the one actually used — and consistent with
        # llama.cpp's ``-c``. The model may support a far larger context, but
        # running it that wide costs a lot of RAM, so we use a sane fixed window.
        self.context_window = context_window
        # Real token counts from the last generation (Ollama reports these), so the
        # UI can show exact usage instead of a character-based estimate.
        self.last_prompt_tokens: int | None = None
        self.last_completion_tokens: int | None = None

    @property
    def model_name(self) -> str:
        return self.model

    def _options(self, temperature: float | None) -> dict[str, object]:
        options: dict[str, object] = {"num_ctx": self.context_window}
        if temperature is not None:
            options["temperature"] = temperature
        return options

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
        response_format: dict | None = None,
    ) -> str:
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        prompt = _with_history(prompt, history)
        response = self._request_with_one_local_retry(
            prompt, images, temperature, think, response_format
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaLLMProviderError("Ollama generation response was not valid JSON") from exc

        if isinstance(payload, dict):
            self.last_prompt_tokens = _coerce_int(payload.get("prompt_eval_count"))
            self.last_completion_tokens = _coerce_int(payload.get("eval_count"))

        generated_text = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(generated_text, str) or not generated_text.strip():
            raise OllamaLLMProviderError("Ollama generation response did not include response text")

        # Reasoning models (deepseek-r1, qwq, …) return their chain-of-thought in
        # a separate "thinking" field. Re-wrap it as <think>…</think> so the UI can
        # show it in a collapsible block. Models that don't think are unaffected.
        thinking = payload.get("thinking") if isinstance(payload, dict) else None
        if isinstance(thinking, str) and thinking.strip():
            return f"<think>\n{thinking.strip()}\n</think>\n\n{generated_text}"

        return generated_text

    def generate_stream(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]:
        """Yield answer text deltas as Ollama produces them.

        Reasoning models stream their chain-of-thought in a separate ``thinking``
        field; it's wrapped as ``<think>…</think>`` ahead of the answer so the UI
        renders the same collapsible block it shows for non-streamed answers.
        """
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": _with_history(prompt, history),
            "stream": True,
        }
        if think is not None:
            payload["think"] = think
        if images:
            payload["images"] = images
        payload["options"] = self._options(temperature)

        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        think_open = False
        think_closed = False
        try:
            for stream_attempt in range(2):
                with self.client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout_seconds,
                ) as response:
                    if response.status_code >= 400:
                        body = response.read().decode("utf-8", "replace").strip()[:300]
                        if response.status_code == 404:
                            raise OllamaLLMProviderError(
                                f"Ollama model '{self.model}' is not installed at "
                                f"{self.base_url}. Refresh Installed Models or download "
                                f"it first. {body}"
                            )
                        # Non-reasoning model rejected `think` — drop it and retry
                        # once so the Reasoning toggle never breaks a normal model.
                        if (
                            stream_attempt == 0
                            and "think" in payload
                            and response.status_code == 400
                            and "think" in body.lower()
                        ):
                            payload.pop("think", None)
                            continue
                        raise OllamaLLMProviderError(
                            f"Ollama streaming request failed ({response.status_code}). {body}"
                        )

                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except ValueError:
                            continue
                        if not isinstance(data, dict):
                            continue

                        thinking = data.get("thinking")
                        if isinstance(thinking, str) and thinking:
                            if not think_open:
                                yield "<think>\n"
                                think_open = True
                            yield thinking

                        chunk = data.get("response")
                        if isinstance(chunk, str) and chunk:
                            if think_open and not think_closed:
                                yield "\n</think>\n\n"
                                think_closed = True
                            yield chunk

                        if data.get("done"):
                            # Final chunk carries the real token counts.
                            self.last_prompt_tokens = _coerce_int(data.get("prompt_eval_count"))
                            self.last_completion_tokens = _coerce_int(data.get("eval_count"))
                            break
                    break
        except httpx.TimeoutException as exc:
            raise OllamaLLMProviderError(
                f"Ollama LLM stream timed out after {self.timeout_seconds} seconds "
                f"for model '{self.model}'."
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaLLMProviderError(
                f"Unable to reach Ollama streaming API at {self.base_url} for model '{self.model}'."
            ) from exc

        if think_open and not think_closed:
            yield "\n</think>\n\n"

    def _request_with_one_local_retry(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        response_format: dict | None = None,
    ) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if think is not None:
            # Toggle reasoning on thinking-capable models (deepseek-r1, qwq, …).
            payload["think"] = think
        if images:
            # Ollama accepts base64-encoded images for vision-capable models.
            payload["images"] = images
        # Constrain output to a JSON Schema (or "json") when the caller asked for
        # structured output — Ollama's equivalent of llama.cpp's grammar.
        ollama_format = ollama_format_from_response_format(response_format)
        if ollama_format is not None:
            payload["format"] = ollama_format
        # Ollama generation tuning (incl. the pinned context window) goes here.
        payload["options"] = self._options(temperature)
        attempt = 0
        while attempt < 2:
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
                # Non-reasoning models reject the `think` flag with a 400. Drop it
                # and retry so the Reasoning toggle never breaks a normal model.
                if "think" in payload and _is_thinking_unsupported(exc.response):
                    payload.pop("think", None)
                    continue
                # An older Ollama that doesn't accept a schema ``format`` returns
                # 400 — drop the constraint and retry so structured callers still
                # get a (free-form) answer instead of a hard failure.
                if "format" in payload and exc.response.status_code == 400:
                    payload.pop("format", None)
                    continue
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc

            attempt += 1
            if attempt < 2:
                sleep(0.25)

        if isinstance(last_error, httpx.HTTPStatusError):
            detail = last_error.response.text.strip()[:300]
            raise OllamaLLMProviderError(
                f"Ollama rejected the request for model '{self.model}' "
                f"({last_error.response.status_code}). {detail}"
            ) from last_error

        if isinstance(last_error, httpx.TimeoutException):
            raise OllamaLLMProviderError(
                f"Ollama LLM request timed out after {self.timeout_seconds} seconds. "
                f"The app retried model '{self.model}' once; the model may still be loading."
            ) from last_error
        raise OllamaLLMProviderError(
            f"Unable to reach Ollama generation API at {self.base_url}. "
            f"The app retried model '{self.model}' once."
        ) from last_error
