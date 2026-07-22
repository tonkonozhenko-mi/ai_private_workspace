"""Turning "qwen3 8b" into something you can actually download.

To add a model, the app used to need the exact identifier of a Hugging Face
repository — including the `-GGUF` suffix and the username of whoever did the
quantizing. Somebody who knows they want Qwen3 8B has no way to reach
`bartowski/Qwen3-8B-GGUF` from that knowledge, and the field offered no help.
It was a text box that required you to already have the answer.

This module holds the pure part of fixing that: how a person's words become a
query, and how the results are ordered so the useful ones are near the top.
The network call itself lives in an adapter — this stays testable.

Ranking is deliberately simple and explainable. Downloads are a decent proxy for
"this is the build people actually use", but on their own they bury a small new
model under a famous old one, so an exact name match outranks popularity. There
is no cleverness here beyond that, and there should not be: a search that
reorders results for reasons the person cannot see is worse than one that misses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Hugging Face publishes quantized models in repositories whose names almost
# always carry this marker. Searching for it is what keeps the results to things
# this app can actually run.
GGUF_MARKER = "gguf"

_WORD = re.compile(r"[a-z0-9.]+")


@dataclass(frozen=True)
class ModelSearchResult:
    """One repository that might hold the model someone is looking for."""

    repo_id: str
    downloads: int = 0
    likes: int = 0
    updated_at: str = ""
    # Filled in later, by asking the repository what files it has. Absent here
    # because finding candidates and sizing them are separate round trips, and
    # making the search wait for sizes would make the search feel broken.
    size_bytes: int = 0

    @property
    def owner(self) -> str:
        return self.repo_id.split("/")[0] if "/" in self.repo_id else ""

    @property
    def model_name(self) -> str:
        return self.repo_id.split("/")[-1]


def build_search_query(words: str) -> str:
    """What to ask Hugging Face, given what the person typed.

    Appending the GGUF marker is the whole trick: without it, searching "qwen3"
    returns the original weights, which this app cannot load, and the person
    concludes the feature is broken rather than that they searched wrong.
    """
    text = (words or "").strip()
    if not text:
        return ""
    if GGUF_MARKER in text.lower():
        return text
    return f"{text} {GGUF_MARKER.upper()}"


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def relevance(result: ModelSearchResult, words: str) -> tuple:
    """Sort key, best first. Returned as a tuple so ordering stays total and
    deterministic — two runs of the same search must not disagree."""
    wanted = _tokens(words)
    name = result.model_name.lower()
    name_tokens = set(_tokens(name))

    # Every word the person typed appears in the repository name: this is very
    # probably the thing they meant.
    all_words_present = all(word in name for word in wanted) if wanted else False
    matched = sum(1 for word in wanted if word in name_tokens)

    return (
        0 if all_words_present else 1,
        -matched,
        -result.downloads,
        -result.likes,
        result.repo_id,
    )


def rank_search_results(
    results: list[ModelSearchResult],
    words: str,
    *,
    limit: int = 20,
) -> list[ModelSearchResult]:
    """Order candidates so the obvious answer is first, and drop the rest.

    Repositories without the GGUF marker are removed rather than ranked low:
    this app cannot load them at all, and offering something unusable is worse
    than offering less.
    """
    usable = [r for r in results or [] if GGUF_MARKER in r.repo_id.lower()]
    usable.sort(key=lambda r: relevance(r, words))
    return usable[:limit]


def no_results_message(words: str) -> str:
    """What to say when the search finds nothing, without blaming the person."""
    text = (words or "").strip()
    if not text:
        return "Type the name of a model — for example, 'qwen3 8b' or 'llama 3.2'."
    return (
        f"No downloadable version of '{text}' found. Either the name is slightly "
        f"different, or nobody has published this model in a format this app can "
        f"run yet."
    )
