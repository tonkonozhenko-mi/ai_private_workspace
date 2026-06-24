"""Optional LLM query rewrite for retrieval.

A user's question is phrased for a human, not for a search index: it carries
pronouns ("how do I disable it?"), intent words ("why", "should I"), and rarely
the exact identifiers that live in the code. This module asks the already-loaded
answer model to distil the question into a compact keyword query before
retrieval runs, so dense + keyword search land on the right files.

Everything here is pure and defensive: the prompt is deterministic, and
``parse_rewritten_query`` always falls back to the original question, so a bad or
empty model response can never degrade retrieval below the no-rewrite baseline.
"""

from __future__ import annotations

# A rewrite longer than this many characters is almost certainly the model
# ignoring the instruction (explaining instead of querying) — discard it.
_MAX_REWRITE_CHARS = 240
# Lead-ins a small model tends to prepend; stripped so only the query remains.
_PREFIXES = (
    "search query:",
    "query:",
    "keywords:",
    "answer:",
    "rewritten query:",
)


def build_query_rewrite_prompt(question: str, prior_terms: str | None = None) -> str:
    """A deterministic instruction that turns a question into a search query.

    ``prior_terms`` (recent conversation text) is offered as optional context so a
    bare follow-up still resolves to concrete subjects, without inventing facts.
    """
    context_line = ""
    if prior_terms and prior_terms.strip():
        context_line = (
            "Recent conversation (for context only, do not answer it):\n"
            f"{prior_terms.strip()}\n\n"
        )
    return (
        "You rewrite a question into a short search query for a code/document "
        "search engine. Output ONLY the query: the key nouns, identifiers and "
        "synonyms a relevant file would contain. No explanation, no punctuation "
        "beyond spaces, at most 12 words. Keep concrete names from the question.\n\n"
        f"{context_line}"
        f"Question: {question.strip()}\n"
        "Search query:"
    )


def parse_rewritten_query(raw: str, original: str) -> str:
    """Sanitise the model's reply into a usable query, or fall back to ``original``.

    Drops common lead-in prefixes and surrounding quotes, keeps a single line, and
    rejects empty, over-long, or degenerate replies so retrieval never regresses.
    """
    if not raw or not raw.strip():
        return original
    text = raw.strip().splitlines()[0].strip()
    lowered = text.lower()
    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    text = text.strip().strip('"').strip("'").strip()
    if not text or len(text) > _MAX_REWRITE_CHARS:
        return original
    return text


def merge_queries(original: str, rewritten: str) -> str:
    """Combine the original question with the rewrite so retrieval keeps the
    user's exact wording *and* gains the expanded terms. Identical or contained
    rewrites collapse to a single copy."""
    original = original.strip()
    rewritten = rewritten.strip()
    if not rewritten or rewritten.casefold() in original.casefold():
        return original
    return f"{original}\n{rewritten}"
