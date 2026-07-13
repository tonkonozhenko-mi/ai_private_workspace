"""The Ukrainian-chat overflow, in tests.

The live failure was ``n_prompt_tokens 8869, n_ctx 8192``: the budget believed a
Cyrillic prompt cost 4 characters per token, the question was never counted at
all, and when the engine refused, the app blamed the engine ("check that it is
running"). These tests pin each of the three.
"""

import json

import httpx
import pytest

from app.adapters.llm.llama_server_llm_provider import (
    LlamaServerLLMProvider,
    LlamaServerLLMProviderError,
)
from app.adapters.llm.ollama_llm_provider import OllamaLLMProvider
from app.core.domain.context_budget import (
    chunk_token_budget,
    estimate_tokens,
    fit_context_results_by_tokens,
    shrink_to_window,
)
from app.core.domain.indexing import ContextSearchResult
from app.core.domain.llm_errors import ContextOverflowError, context_overflow_answer

CYRILLIC = "як налаштовано термінал і бекенд у цьому проєкті"


def _result(chunk_id: str, content: str) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=chunk_id,
        source_path=f"{chunk_id}.md",
        content=content,
        score=1.0,
        metadata={},
    )


# --- the estimate knows what script it is looking at ---------------------------


def test_estimate_is_script_aware():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 40) == 10
    # Cyrillic costs about twice as many tokens as the same length of ASCII.
    assert estimate_tokens("я" * 40) == 20
    # CJK costs about one token per character.
    assert estimate_tokens("字" * 40) == 40


def test_mixed_text_counts_each_script():
    mixed = "abcd" + "яя"
    assert estimate_tokens(mixed) == 1 + 1


def test_cyrillic_costs_more_budget_than_ascii():
    ascii_budget = chunk_token_budget(8192, question="a" * 400)
    cyrillic_budget = chunk_token_budget(8192, question="я" * 400)
    assert cyrillic_budget < ascii_budget


# --- the question and the extras are part of the prompt ------------------------


def test_question_and_extras_are_counted():
    bare = chunk_token_budget(8192)
    with_question = chunk_token_budget(8192, question="q" * 4000)
    with_extra = chunk_token_budget(8192, extra_text="e" * 4000)
    assert with_question < bare
    assert with_extra < bare


# --- nothing we send exceeds the window ---------------------------------------


def test_fitting_respects_a_token_budget():
    results = [_result(str(i), "a" * 400) for i in range(10)]  # 100 tokens each
    fitted = fit_context_results_by_tokens(results, token_budget=260)
    assert [r.chunk_id for r in fitted] == ["0", "1"]


def test_a_lone_oversized_chunk_is_truncated():
    fitted = fit_context_results_by_tokens([_result("big", "z" * 8000)], token_budget=100)
    assert len(fitted) == 1
    assert 0 < len(fitted[0].content) < 8000


def test_shrink_to_window_never_exceeds_the_window():
    """A tokenizer that charges 2 chars per token — Mistral on Cyrillic — and an
    8192 window: whatever survives must fit, with the answer headroom intact."""

    def count(text: str) -> int:
        return len(text) // 2

    chunks = [_result(str(i), "я" * 4000) for i in range(12)]

    def build(kept: list[ContextSearchResult]) -> str:
        return "SCAFFOLD" * 100 + "".join(chunk.content for chunk in kept)

    kept, prompt = shrink_to_window(chunks, build, 8192, token_counter=count)
    assert count(prompt) <= 8192 - 768
    assert len(kept) < len(chunks)


def test_shrink_keeps_everything_when_it_already_fits():
    chunks = [_result("only", "short")]
    kept, prompt = shrink_to_window(chunks, lambda c: "text", 8192)
    assert kept == chunks


# --- the engine's refusal is understood, not misreported ------------------------


def _overflow_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        400,
        json={
            "error": {
                "code": 400,
                "message": "the request exceeds the available context size",
                "type": "exceed_context_size_error",
                "n_prompt_tokens": 8869,
                "n_ctx": 8192,
            }
        },
    )


def test_llama_server_reports_a_context_overflow_not_a_dead_engine():
    client = httpx.Client(transport=httpx.MockTransport(_overflow_response))
    provider = LlamaServerLLMProvider(base_url="http://localhost:8080", model="m", client=client)
    with pytest.raises(ContextOverflowError) as caught:
        provider.generate("prompt")
    assert caught.value.prompt_tokens == 8869
    assert caught.value.context_window == 8192
    assert not isinstance(caught.value, LlamaServerLLMProviderError)


def test_other_400s_stay_ordinary_engine_errors():
    def bad_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "model not loaded"}})

    client = httpx.Client(transport=httpx.MockTransport(bad_request))
    provider = LlamaServerLLMProvider(base_url="http://localhost:8080", model="m", client=client)
    with pytest.raises(LlamaServerLLMProviderError):
        provider.generate("prompt")


def test_overflow_ratio_sizes_the_retry_to_the_overshoot():
    error = ContextOverflowError("too long", prompt_tokens=8869, context_window=8192)
    # 8192/8869 ≈ 0.92, minus 10% headroom.
    assert 0.8 < error.overflow_ratio < 0.85
    # No numbers from the engine: halve and try again.
    assert ContextOverflowError("too long").overflow_ratio == 0.5


def test_the_message_blames_the_prompt_not_the_engine():
    message = context_overflow_answer(
        ContextOverflowError("too long", prompt_tokens=8869, context_window=8192)
    )
    assert "8,869" in message and "8,192" in message
    assert "retried" in message
    assert "running" not in message


# --- both engines can be asked how much memory they actually have ---------------


def test_llama_server_reads_its_real_window_from_props():
    def props(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/props"
        return httpx.Response(200, json={"default_generation_settings": {"n_ctx": 8192}})

    client = httpx.Client(transport=httpx.MockTransport(props))
    provider = LlamaServerLLMProvider(base_url="http://localhost:8080", model="m", client=client)
    assert provider.context_window == 8192


def test_ollama_never_pins_a_window_larger_than_the_model_supports():
    """A model whose weights stop at 2048 gets 2048 — our 8192 floor is a default,
    not a promise the model can keep."""

    def show(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/show"
        assert json.loads(request.content)["model"] == "phi3"
        return httpx.Response(200, json={"model_info": {"phi3.context_length": 2048}})

    client = httpx.Client(transport=httpx.MockTransport(show))
    provider = OllamaLLMProvider(
        base_url="http://localhost:11434", model="phi3", client=client, context_window=4096
    )
    assert provider.context_window == 2048


def test_ollama_keeps_the_requested_window_when_the_model_is_silent():
    def show(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(show))
    provider = OllamaLLMProvider(
        base_url="http://localhost:11434", model="m", client=client, context_window=4096
    )
    assert provider.context_window == 4096
