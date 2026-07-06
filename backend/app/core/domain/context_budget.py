"""Token-budgeted context fitting for the Ask prompt.

The model has a fixed context window (e.g. 8192 tokens). The grounded prompt is
the sum of: a fixed instruction scaffold, the project-memory section, the
conversation history (sent as separate chat messages but still consuming the
window), and the retrieved context chunks — plus headroom reserved for the
answer the model is about to write.

Previously the Ask path concatenated *all* retrieved chunks and hoped they fit;
when they didn't, the engine silently truncated. This module sizes the chunk
content to what actually fits, so nothing is dropped without our knowledge.

Everything here is pure and deterministic (token counts are estimated at a rough
4-chars-per-token ratio), so it is trivial to test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from app.core.domain.indexing import ContextSearchResult

# Rough average for English/code; good enough for budgeting, not exact tokenizing.
CHARS_PER_TOKEN = 4
# Headroom kept free for the model's answer.
RESPONSE_RESERVE_TOKENS = 768
# The fixed instruction text + per-chunk framing in the grounded prompt.
PROMPT_SCAFFOLD_TOKENS = 900
# Never starve the context entirely, even with a tiny window.
MIN_CHUNK_CHARS = 600
# Per-chunk framing ("[n] source_path: …\nchunk_id: …\ncontent:\n") overhead, chars.
_PER_CHUNK_OVERHEAD_CHARS = 80

_DEFAULT_CONTEXT_WINDOW = 8192


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def chunk_char_budget(
    context_window: int | None,
    *,
    memory_text: str = "",
    history: list[tuple[str, str]] | None = None,
    response_reserve_tokens: int = RESPONSE_RESERVE_TOKENS,
    scaffold_tokens: int = PROMPT_SCAFFOLD_TOKENS,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
    token_counter: Callable[[str], int] | None = None,
) -> int:
    """How many characters of retrieved-chunk content fit, given everything else
    that shares the window (scaffold, memory, history) and the answer headroom.

    ``token_counter`` optionally supplies an *exact* token count for a string
    (e.g. the engine's tokenizer); when ``None`` we fall back to the rough
    4-chars-per-token estimate. Either way the result stays a character budget.
    """
    count = token_counter or estimate_tokens
    window = context_window if (context_window and context_window > 0) else _DEFAULT_CONTEXT_WINDOW
    used_tokens = response_reserve_tokens + scaffold_tokens
    used_tokens += count(memory_text)
    for _role, content in history or []:
        used_tokens += count(content)
    remaining_tokens = window - used_tokens
    return max(min_chunk_chars, remaining_tokens * CHARS_PER_TOKEN)


# Upper bound on the characters one stored chunk contributes to the prompt: the
# structure-aware chunker's body cap (~1500) + a contextual header + per-chunk
# framing. Deliberately generous (≈2x a typical chunk) so the "whole project
# fits" decision is conservative and needs no content read — the slack also
# absorbs the memory/history the gate doesn't measure.
FULL_CONTEXT_PER_CHUNK_CHARS = 1500 + 120 + _PER_CHUNK_OVERHEAD_CHARS
# Stay below the hard budget so fit_context_results never has to trim a file.
FULL_CONTEXT_FILL_RATIO = 0.9


def project_fits_whole_context(
    chunks_count: int,
    context_window: int | None,
    *,
    memory_text: str = "",
    history: list[tuple[str, str]] | None = None,
    token_counter: Callable[[str], int] | None = None,
) -> bool:
    """True when every indexed chunk provably fits the prompt at once.

    On a small project the whole codebase fits the window, so retrieval only adds
    the risk of missing the right file. When this returns True the caller may skip
    retrieval and feed all files wholesale. Uses a generous per-chunk ceiling, so
    the decision is deterministic and needs no content read; ``fit_context_results``
    remains the final guard against overflow.
    """
    if chunks_count <= 0:
        return False
    budget = chunk_char_budget(
        context_window,
        memory_text=memory_text,
        history=history,
        token_counter=token_counter,
    )
    return chunks_count * FULL_CONTEXT_PER_CHUNK_CHARS <= budget * FULL_CONTEXT_FILL_RATIO


def fit_context_results(
    results: list[ContextSearchResult],
    char_budget: int,
) -> list[ContextSearchResult]:
    """Keep as many whole chunks as fit ``char_budget``; if even the first chunk
    is too large, truncate it so the prompt never overflows. Order is preserved
    (best-ranked first), so the most relevant context is what survives."""
    if char_budget <= 0:
        return results[:1] if results else []
    kept: list[ContextSearchResult] = []
    used = 0
    for result in results:
        cost = len(result.content) + _PER_CHUNK_OVERHEAD_CHARS
        if used + cost <= char_budget:
            kept.append(result)
            used += cost
            continue
        if kept:
            break
        # First chunk alone exceeds the budget: truncate it to fit.
        remaining = max(0, char_budget - _PER_CHUNK_OVERHEAD_CHARS)
        kept.append(replace(result, content=result.content[:remaining]))
        break
    return kept
