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

from app.core.domain.chat_turns import turns_before_user_message
from app.core.domain.context_budget import estimate_tokens
from app.core.domain.degenerate_output import looping_paragraph
from app.core.domain.llm_errors import ContextOverflowError

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


def _context_overflow(status_code: int, body: str) -> ContextOverflowError | None:
    """Recognise llama-server's "the prompt didn't fit" 400.

    The body is ``{"error": {"type": "exceed_context_size_error", "message": "…",
    "n_prompt_tokens": 8869, "n_ctx": 8192}}``. Those two numbers are the truth
    about the window — worth carrying, because the caller can retry with less
    context and, failing that, tell the person exactly what didn't fit.
    """
    if status_code != 400 or "exceed_context_size_error" not in body:
        return None
    prompt_tokens: int | None = None
    window: int | None = None
    message = "The prompt was longer than the model's context window."
    try:
        error = json.loads(body).get("error")
    except ValueError:
        error = None
    if isinstance(error, dict):
        for key in ("n_prompt_tokens", "n_prompt_tokens_total"):
            value = error.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                prompt_tokens = value
                break
        n_ctx = error.get("n_ctx")
        if isinstance(n_ctx, int) and not isinstance(n_ctx, bool):
            window = n_ctx
        text = error.get("message")
        if isinstance(text, str) and text.strip():
            message = text.strip()
    return ContextOverflowError(message, prompt_tokens=prompt_tokens, context_window=window)


class LlamaServerLLMProvider:
    provider_name = "llamacpp"
    # llama-server builds a grammar from ``response_format``, so it can be made to
    # emit only schema-valid JSON. Consumers detect this to switch on structured
    # output (e.g. the Investigator's tool-call steps).
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
        instead of us flattening the dialogue into one text blob.

        Shaped to what a chat template will accept, because several of them
        (Mistral's included) raise rather than cope, and a raised template costs
        the whole answer. The prompt below is a user message, so the history must
        not end with one either — see chat_turns for what that costs us and why
        nothing is thrown away to achieve it.
        """
        return [
            {"role": role, "content": content}
            for role, content in turns_before_user_message(history)
        ]

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
        response_format: dict | None = None,
    ) -> dict:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": self._build_messages(prompt, images, history),
            "stream": stream,
            "stop": _STOP_TOKENS,
            # Reuse the KV cache for the shared prompt prefix across turns of a
            # conversation (system + context + requirements are kept stable and the
            # volatile question is last), so multi-turn answers start faster.
            "cache_prompt": True,
            # Ask the engine not to loop. We were sending nothing here, and
            # llama.cpp's default barely penalises repetition — which is how a
            # good answer turned into the same paragraph ten times over. 1.1 over
            # the last 256 tokens is the conservative end of the usual range: it
            # discourages a cycle without pushing the model off vocabulary it
            # legitimately needs (a file path repeated in three sentences is not
            # a loop, and this must not make it one).
            "repeat_penalty": 1.1,
            "repeat_last_n": 256,
        }
        if response_format is not None:
            # Constrain generation to a JSON Schema / object so the model cannot
            # emit invalid JSON — llama.cpp builds a grammar from this.
            payload["response_format"] = response_format
        if stream:
            # Ask for a trailing usage chunk so streamed answers also report real
            # token counts (otherwise the stream carries only text deltas).
            payload["stream_options"] = {"include_usage": True}
        if temperature is not None:
            payload["temperature"] = temperature
        return payload

    def count_tokens(self, text: str) -> int:
        """Exact token count for ``text`` via llama-server's ``/tokenize``.

        Falls back to a ~4-chars-per-token estimate on any error, so callers can
        use it unconditionally for context budgeting.
        """
        if not text:
            return 0
        try:
            response = self.client.post(
                f"{self.base_url}/tokenize",
                json={"content": text},
                timeout=min(self.timeout_seconds, 10),
            )
            if response.status_code < 400:
                tokens = response.json().get("tokens")
                if isinstance(tokens, list):
                    return len(tokens)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass
        # Script-aware estimate: a Cyrillic question costs ~2 chars/token, not 4.
        return max(1, estimate_tokens(text))

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
        try:
            response = self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json=self._payload(
                    prompt,
                    images,
                    temperature,
                    stream=False,
                    history=history,
                    response_format=response_format,
                ),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise LlamaServerLLMProviderError(
                f"Could not reach llama-server at {self.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            body = response.text.strip()
            overflow = _context_overflow(response.status_code, body)
            if overflow is not None:
                raise overflow
            raise LlamaServerLLMProviderError(
                f"llama-server returned HTTP {response.status_code}: {body[:300]}"
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
        response_format: dict | None = None,
    ) -> Iterator[str]:
        """Yield answer text deltas via the OpenAI-compatible SSE stream."""
        streamed: list[str] = []
        self.last_prompt_tokens = None
        self.last_completion_tokens = None
        try:
            with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=self._payload(
                    prompt,
                    images,
                    temperature,
                    stream=True,
                    history=history,
                    response_format=response_format,
                ),
                timeout=self.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    body = response.read().decode("utf-8", "replace").strip()
                    overflow = _context_overflow(response.status_code, body)
                    if overflow is not None:
                        raise overflow
                    raise LlamaServerLLMProviderError(
                        f"llama-server returned HTTP {response.status_code}: {body[:300]}"
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
                        # A model that has begun repeating itself will keep
                        # going until the token limit — minutes of the person's
                        # machine spent printing one paragraph, which they then
                        # have to interrupt themselves. Checked on the text that
                        # actually arrived, not on what we hoped for.
                        streamed.append(delta)
                        if looping_paragraph("".join(streamed)) is not None:
                            break
        except httpx.HTTPError as exc:
            raise LlamaServerLLMProviderError(
                f"Could not stream from llama-server at {self.base_url}: {exc}"
            ) from exc
