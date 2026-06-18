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
        # llama-server is launched with ``-c 4096`` (see LlamaServerProcessManager),
        # so this is the real per-request token window. Surfaced for the UI.
        self.context_window = context_window

    @property
    def model_name(self) -> str:
        return self.model

    def _build_messages(self, prompt: str, images: list[str] | None) -> list[dict]:
        if not images:
            return [{"role": "user", "content": prompt}]
        # OpenAI-style multimodal content parts (supported by multimodal GGUFs
        # served with a projector). Plain-text models ignore images upstream.
        parts: list[dict] = [{"type": "text", "text": prompt}]
        for image in images:
            data_url = image if image.startswith("data:") else f"data:image/png;base64,{image}"
            parts.append({"type": "image_url", "image_url": {"url": data_url}})
        return [{"role": "user", "content": parts}]

    def _payload(
        self, prompt: str, images: list[str] | None, temperature: float | None, stream: bool
    ) -> dict:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._build_messages(prompt, images),
            "stream": stream,
            "stop": _STOP_TOKENS,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def generate(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> str:
        try:
            response = self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=self._payload(prompt, images, temperature, stream=False),
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

        if not isinstance(content, str) or not content.strip():
            raise LlamaServerLLMProviderError("llama-server returned an empty answer")
        return _clean(content).strip()

    def generate_stream(
        self,
        prompt: str,
        images: list[str] | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> Iterator[str]:
        """Yield answer text deltas via the OpenAI-compatible SSE stream."""
        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=self._payload(prompt, images, temperature, stream=True),
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
                        delta = chunk["choices"][0]["delta"].get("content")
                    except (ValueError, KeyError, IndexError, TypeError):
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
