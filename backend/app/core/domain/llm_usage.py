from __future__ import annotations

from dataclasses import dataclass


def estimate_llm_tokens(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    # Lightweight local estimate for UI telemetry only.
    return max(1, round(len(stripped) / 4))


@dataclass(frozen=True)
class LLMUsageMetrics:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    tokens_per_second: float | None = None
    provider: str | None = None
    model: str | None = None
    estimated: bool = False


def build_llm_usage_metrics(
    *,
    prompt: str,
    completion: str,
    latency_ms: int | None,
    provider: str | None,
    model: str | None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated: bool = True,
) -> LLMUsageMetrics:
    prompt_token_count = prompt_tokens if prompt_tokens is not None else estimate_llm_tokens(prompt)
    completion_token_count = (
        completion_tokens if completion_tokens is not None else estimate_llm_tokens(completion)
    )
    total_token_count = (
        total_tokens
        if total_tokens is not None
        else prompt_token_count + completion_token_count
    )
    tokens_per_second = None
    if latency_ms is not None and latency_ms > 0 and completion_token_count is not None:
        tokens_per_second = round(completion_token_count / (latency_ms / 1000), 2)

    return LLMUsageMetrics(
        prompt_tokens=prompt_token_count,
        completion_tokens=completion_token_count,
        total_tokens=total_token_count,
        latency_ms=latency_ms,
        tokens_per_second=tokens_per_second,
        provider=provider,
        model=model,
        estimated=estimated,
    )
