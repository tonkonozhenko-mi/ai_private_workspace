"""LLM provider that talks to a local ``llama-server`` (llama.cpp) over HTTP.

This is the Ollama-free path: when the app bundles llama.cpp's ``llama-server``
binary, it exposes an OpenAI-compatible HTTP API (default
``http://127.0.0.1:8080``). We send the already-built RAG prompt as a single
user message so the server applies the model's own chat template, exactly the
way the Ollama provider relies on Ollama to template ``/api/generate`` prompts.

``llama-server`` loads one GGUF model at startup, so ``model`` here is mostly a
label; the running server decides which weights answer. Reasoning models emit
their chain-of-thought inline as ``<think>…</think>`` in the content, which the
UI already renders, so no special "thinking" field handling is needed.
"""

import json
from collections.abc import Iterator

import httpx

# Chat-template control tokens (Llama 3 / Qwen / ChatML …). A model occasionally
# emits these into the text; we ask the server to stop on them and, as a safety
# net, cut the answer at the first one — everything after a ``<|`` marker is
# template machinery (header roles, end-of-turn), never real answer content.
_STOP_TOKENS = ["<|eot_id|>", "<|end_of_text|>", "<|im_end|>", "<|eom_id|>"]


def _clean(text: str) -> str:
    index = text.find("<|")
    return text[:index] if index != -1 else text


class LlamaServerLLMProviderError(RuntimeError):
    pass


class LlamaServerLLMProvider:
    provider_name = "llamacpp"

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
        # Fallback window if /props can't be read; the real value is fetched live.
        self._declared_context_window = context_window
        self._context_window_cache: int | None = None
        # Real token counts from the last generation (llama-server reports usage).
        self.last_prompt_tokens: int | None = None
        self.last_completion_tokens: int | None = None

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def context_window(self) -> int:
        """The server's real context size (``n_ctx``), read from /props once.

        This reflects what llama-server actually loaded (the ``-c`` value), so the
        UI shows the true window rather than a guess. Falls back to the declared
        default if /props is unavailable.
        """
        if self._context_window_cache is not None:
            return self._context_window_cache
        n_ctx = self._declared_context_window
        try:
            response = self.client.get(f"{self.base_url}/props", timeout=self.timeout_seconds)
            if response.status_code < 400:
                data = response.json()
                if isinstance(data, dict):
                    candidate = data.get("n_ctx")
                    settings = data.get("default_generation_settings")
                    if candidate is None and isinstance(settings, dict):
                        candidate = settings.get("n_ctx")
                    if (
                        isinstance(candidate, int)
                        and not isinstance(candidate, bool)
                        and candidate > 0
                    ):
                        n_ctx = candidate
        except (httpx.HTTPError, ValueError):
            pass
        self._context_window_cache = n_ctx
        return n_ctx

    def _capture_usage(self, payload: object) -> None:
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if not isinstance(usage, dict):
            return
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool):
            self.last_prompt_tokens = prompt_tokens
        if isinstance(completion_tokens, int) and not isinstance(completion_tokens, bool):
            self.last_completion_tokens = completion_tokens

    @staticmethod
    def _history_messages(history: list[tuple[str, str]] | None) -> list[dict]:
        """Prior turns as real chat messages so the model keeps conversational
        context (resolves "it"/"that", follows up) the way ChatGPT/Claude do —
        instead of us flattening the dialogue into one text blob."""
        if not history:
            return []
        messages: list[dict] = []
        for role, content in history:
            normalized = "assistant" if role == "assistant" else "user"
            text = content.strip()
            if text:
                messages.append({"role": normalized, "content": text})
        return messages

    def _build_messages(
        self,
        prompt: str,
        images: list[str] | None,
        history: list[tuple[str, str]] | None = None,
    ) -> list[dict]:
        history_messages = self._history_messages(history)
        if not images:
            return [*history_messages, {"role": "user", "content": prompt}]
        # OpenAI-style multimodal content parts (supported by multimodal GGUFs
        # served with a projector). Plain-text models ignore images upstream.
        parts: list[dict] = [{"type": "text", "text": prompt}]
        for image in images:
            data_url = image if image.startswith("data:") else f"data:image/png;base64,{image}"
            parts.append({"type": "image_url", "image_url": {"url": data_url}})
        return [*history_messages, {"role": "user", "content": parts}]

    def _payload(
        self,
        prompt: str,
        images: list[str] | None,
        temperature: float | None,
        stream: bool,
        history: list[tuple[str, str]] | None = None,
    ) -> dict:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._build_messages(prompt, images, history),
            "stream": stream,
            "stop": _STOP_TOKENS,
        }
        if stream:
            # Ask for a trailing usage chunk so streamed answers also report real
            # token counts (otherwise the stream carries only text deltas).
            payload["stream_options"] = {"include_usage": True}
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        try:
            response = self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=self._payload(prompt, images, temperature, stream=False, history=history),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise LlamaServerLLMProviderError(
                f"Could not reach llama-server at {self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            body = response.text.strip()[:300]
            raise LlamaServerLLMProviderError(
                f"llama-server returned HTTP {response.status_code}: {body}"
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlamaServerLLMProviderError(
                "llama-server response did not include a message"
            ) from exc

        self._capture_usage(payload)

        if not isinstance(content, str) or not content.strip():
            raise LlamaServerLLMProviderError("llama-server returned an empty answer")
        return _clean(content).strip()

    def generate_stream(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
        history: list[tuple[str, str]] | None = None,
    ) -> Iterator[str]:
        """Yield answer text deltas via the OpenAI-compatible SSE stream."""
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=self._payload(prompt, images, temperature, stream=True, history=history),
                timeout=self.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    body = response.read().decode("utf-8", "replace").strip()[:300]
                    raise LlamaServerLLMProviderError(
                        f"llama-server returned HTTP {response.status_code}: {body}"
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    # The final usage chunk has empty choices but real token counts.
                    self._capture_usage(chunk)
                    try:
                        delta = chunk["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, TypeError):
                        continue
                    if isinstance(delta, str) and delta:
                        # Stop at the first control token: emit text before it,
                        # then end the stream cleanly.
                        index = delta.find("<|")
                        if index != -1:
                            if delta[:index]:
                                yield delta[:index]
                            break
                        yield delta
        except httpx.HTTPError as exc:
            raise LlamaServerLLMProviderError(
                f"Could not stream from llama-server at {self.base_url}: {exc}"
            ) from exc
