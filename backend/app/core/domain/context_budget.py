"""Token-budgeted context fitting for the Ask prompt.

The model has a fixed context window (e.g. 8192 tokens). The grounded prompt is
the sum of: a fixed instruction scaffold, the project-memory section, the
conversation history (sent as separate chat messages but still consuming the
window), and the retrieved context chunks — plus headroom reserved for the
answer the model is about to write.

Previously the Ask path concatenated *all* retrieved chunks and hoped they fit;
when they didn't, the engine silently truncated. This module sizes the chunk
content to what actually fits, so nothing is dropped without our knowledge.

Everything here is pure and deterministic, so it is trivial to test.

Two things the first version of this module got wrong, both of which overflowed
a real 8192-token window:

* it budgeted the scaffold, memory and history but forgot the *question* and the
  role hint — small texts, but they are part of the prompt;
* it assumed 4 characters per token for every script. That holds for English and
  code; Cyrillic costs a Latin-trained tokenizer roughly 2 characters per token,
  CJK closer to 1. A Ukrainian conversation therefore spent about twice the
  tokens the budget believed it was spending.

So token counts here are *script-aware*, and the conversion back from tokens to
a character budget uses the ratio measured on the text actually in play, not a
constant. Where the engine exposes a real tokenizer we prefer it, and
``shrink_to_window`` re-measures the finished prompt as a last guard.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from app.core.domain.indexing import ContextSearchResult

# Rough average for English/code; good enough for budgeting, not exact tokenizing.
CHARS_PER_TOKEN = 4
# Characters per token for non-Latin scripts on a Latin-trained tokenizer.
CYRILLIC_CHARS_PER_TOKEN = 2
CJK_CHARS_PER_TOKEN = 1
# Headroom kept free for the model's answer.
RESPONSE_RESERVE_TOKENS = 768
# The fixed instruction text + per-chunk framing in the grounded prompt.
PROMPT_SCAFFOLD_TOKENS = 900
# Never starve the context entirely, even with a tiny window.
MIN_CHUNK_CHARS = 600
# Per-chunk framing ("[n] source_path: …\nchunk_id: …\ncontent:\n") overhead, chars.
_PER_CHUNK_OVERHEAD_CHARS = 80

# Under-estimating the window is safe (we send less than fits); over-estimating is
# the bug we are fixing. So the fallback, used only when neither engine could tell
# us its real window, is the smallest window any local model ships with.
_DEFAULT_CONTEXT_WINDOW = 4096

# Everything from CJK ideographs upward is roughly one token per character.
_CJK_START = 0x2E80


def estimate_tokens(text: str | None) -> int:
    """A script-aware token estimate: ASCII at ~4 chars/token, Cyrillic/Greek and
    other non-Latin scripts at ~2, CJK at ~1.

    Used whenever the engine exposes no tokenizer (the whole Ollama path). It is
    still an estimate — but one that no longer halves the true cost of a
    Ukrainian question.
    """
    if not text:
        return 0
    ascii_chars = 0
    wide_chars = 0
    cjk_chars = 0
    for character in text:
        code = ord(character)
        if code < 128:
            ascii_chars += 1
        elif code >= _CJK_START:
            cjk_chars += 1
        else:
            wide_chars += 1
    return (
        ascii_chars // CHARS_PER_TOKEN
        + wide_chars // CYRILLIC_CHARS_PER_TOKEN
        + cjk_chars // CJK_CHARS_PER_TOKEN
    )


def effective_chars_per_token(sample: str) -> float:
    """How many characters one token buys *in this conversation*.

    Turning a token budget back into a character budget needs a ratio, and the
    ratio depends on the script: 4 for English/code, ~2 for Cyrillic. We measure
    it on a sample of the text already in the prompt (memory, history, question),
    so the chunk budget speaks the same language as the chunks.
    """
    if not sample:
        return float(CHARS_PER_TOKEN)
    tokens = estimate_tokens(sample)
    if tokens <= 0:
        return float(CHARS_PER_TOKEN)
    ratio = len(sample) / tokens
    # Never claim more than the ASCII ratio, never less than the CJK one.
    return max(float(CJK_CHARS_PER_TOKEN), min(float(CHARS_PER_TOKEN), ratio))


def chunk_char_budget(
    context_window: int | None,
    *,
    memory_text: str = "",
    history: list[tuple[str, str]] | None = None,
    question: str = "",
    extra_text: str = "",
    response_reserve_tokens: int = RESPONSE_RESERVE_TOKENS,
    scaffold_tokens: int = PROMPT_SCAFFOLD_TOKENS,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
    token_counter: Callable[[str], int] | None = None,
) -> int:
    """How many characters of retrieved-chunk content fit, given everything else
    that shares the window (scaffold, memory, history, the question itself and any
    extra sections such as the role hint) and the answer headroom.

    ``token_counter`` optionally supplies an *exact* token count for a string
    (e.g. the engine's tokenizer); when ``None`` we fall back to the script-aware
    estimate. Either way the result stays a character budget, converted at the
    ratio measured on the text in play rather than a fixed 4 chars/token.
    """
    count = token_counter or estimate_tokens
    window = context_window if (context_window and context_window > 0) else _DEFAULT_CONTEXT_WINDOW
    used_tokens = response_reserve_tokens + scaffold_tokens
    used_tokens += count(memory_text)
    used_tokens += count(question)
    used_tokens += count(extra_text)
    for _role, content in history or []:
        used_tokens += count(content)
    remaining_tokens = window - used_tokens
    if remaining_tokens <= 0:
        return min_chunk_chars
    sample = "\n".join(
        [memory_text, question, extra_text, *[content for _role, content in history or []]]
    )
    chars_per_token = effective_chars_per_token(sample)
    return max(min_chunk_chars, int(remaining_tokens * chars_per_token))


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


# Per-chunk framing measured in tokens rather than characters.
_PER_CHUNK_OVERHEAD_TOKENS = 24
# Trim slightly below the window so a tokenizer disagreement of a few tokens
# (ours vs the engine's, on the templated prompt) cannot tip us over.
_SHRINK_SAFETY = 0.95
# One chunk always survives, so an answer is still grounded in something.
_MIN_KEPT_CHUNKS = 1


def chunk_token_budget(
    context_window: int | None,
    *,
    memory_text: str = "",
    history: list[tuple[str, str]] | None = None,
    question: str = "",
    extra_text: str = "",
    response_reserve_tokens: int = RESPONSE_RESERVE_TOKENS,
    scaffold_tokens: int = PROMPT_SCAFFOLD_TOKENS,
    token_counter: Callable[[str], int] | None = None,
) -> int:
    """The same allocation as ``chunk_char_budget``, but left in tokens.

    Tokens are the unit the model actually counts, so chunks are fitted against
    this and never against a character estimate of it.
    """
    count = token_counter or estimate_tokens
    window = context_window if (context_window and context_window > 0) else _DEFAULT_CONTEXT_WINDOW
    used = response_reserve_tokens + scaffold_tokens
    used += count(memory_text) + count(question) + count(extra_text)
    for _role, content in history or []:
        used += count(content)
    return max(0, window - used)


def fit_context_results_by_tokens(
    results: list[ContextSearchResult],
    token_budget: int,
    token_counter: Callable[[str], int] | None = None,
) -> list[ContextSearchResult]:
    """Keep as many whole chunks as fit ``token_budget``, measuring each chunk in
    tokens. If even the best-ranked chunk is too large, truncate it.

    The character-based sibling above is kept for the "does the whole project
    fit" gate, which needs no content; this is what the prompt is actually built
    with.
    """
    count = token_counter or estimate_tokens
    if not results:
        return []
    kept: list[ContextSearchResult] = []
    used = 0
    for result in results:
        cost = count(result.content) + _PER_CHUNK_OVERHEAD_TOKENS
        if used + cost <= token_budget:
            kept.append(result)
            used += cost
            continue
        if kept:
            break
        # Best chunk alone exceeds the budget: cut it to the characters that fit.
        room = max(0, token_budget - _PER_CHUNK_OVERHEAD_TOKENS)
        chars = int(room * effective_chars_per_token(result.content))
        kept.append(replace(result, content=result.content[:chars]))
        break
    return kept


def shrink_to_window(
    results: list[ContextSearchResult],
    build_prompt: Callable[[list[ContextSearchResult]], str],
    context_window: int | None,
    *,
    token_counter: Callable[[str], int] | None = None,
    history: list[tuple[str, str]] | None = None,
    response_reserve_tokens: int = RESPONSE_RESERVE_TOKENS,
    max_iterations: int = 3,
) -> tuple[list[ContextSearchResult], str]:
    """Build the prompt, measure the finished text, and drop trailing chunks until
    it provably fits the window. Returns the surviving chunks and their prompt.

    Every estimate above can be wrong — the chat template adds tokens we never
    see, and without an engine tokenizer we are guessing at the script. This
    measures what we are about to send, which is the only number the engine will
    agree with. It is the last thing between us and ``exceed_context_size_error``.
    """
    count = token_counter or estimate_tokens
    window = context_window if (context_window and context_window > 0) else _DEFAULT_CONTEXT_WINDOW
    limit = int((window - response_reserve_tokens) * _SHRINK_SAFETY)
    history_tokens = sum(count(content) for _role, content in history or [])
    kept = list(results)
    prompt = build_prompt(kept)
    for _attempt in range(max(1, max_iterations)):
        total = count(prompt) + history_tokens
        if total <= limit or limit <= 0:
            return kept, prompt
        if len(kept) > _MIN_KEPT_CHUNKS:
            # Drop the weakest chunks in proportion to the overflow, always at
            # least one — so a 10% overshoot doesn't cost the whole context.
            ratio = max(0.1, limit / total)
            target = max(_MIN_KEPT_CHUNKS, min(len(kept) - 1, int(len(kept) * ratio)))
            kept = kept[:target]
        elif kept:
            # One chunk left and still too long: truncate its content.
            room = max(0, limit - (total - count(kept[0].content)))
            chars = int(room * effective_chars_per_token(kept[0].content))
            if chars <= 0:
                kept = []
            elif chars >= len(kept[0].content):
                return kept, prompt
            else:
                kept = [replace(kept[0], content=kept[0].content[:chars])]
        else:
            return kept, prompt
        prompt = build_prompt(kept)
    return kept, prompt
