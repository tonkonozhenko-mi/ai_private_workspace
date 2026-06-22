"""Project Memory: durable, local notes/decisions/corrections/Q&A about a project.

This is the "learns over time" layer. The app accumulates small pieces of
knowledge — user notes, corrections ("prod is called prd here"), decisions, and
agent Q&A — and feeds the relevant ones back into any LLM call (Ask, Investigator,
overview). No model weights are touched; the knowledge lives in a local store and
is always visible and editable by the user.

Everything here is pure and deterministic: the selection of which memory is
relevant is keyword + pin + recency based, not an LLM guess.
"""

import re
from dataclasses import dataclass


class MemoryKind:
    NOTE = "note"
    DECISION = "decision"
    CORRECTION = "correction"
    QA = "qa"  # an answered question (often captured from the Investigator)
    FACT = "fact"
    HANDBOOK = "handbook"  # the singleton auto-generated project handbook


class MemorySource:
    USER = "user"
    AGENT = "agent"
    AUTO = "auto"


@dataclass(frozen=True)
class MemoryItem:
    id: str
    workspace_id: str
    kind: str
    text: str
    source: str
    created_at: str  # ISO 8601
    pinned: bool = False


_WORD_RE = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2}


def select_relevant_memory(
    items: list[MemoryItem],
    query: str,
    limit: int = 6,
) -> list[MemoryItem]:
    """Rank memory for a query: pinned first, then keyword overlap, then recency.

    The handbook is handled separately by the context composer, so it is excluded
    here to avoid duplicating it.
    """
    query_tokens = _tokens(query)
    candidates = [i for i in items if i.kind != MemoryKind.HANDBOOK]

    def score(item: MemoryItem) -> tuple:
        overlap = len(_tokens(item.text) & query_tokens)
        return (1 if item.pinned else 0, overlap, item.created_at)

    ranked = sorted(candidates, key=score, reverse=True)
    # Keep items that are pinned or actually overlap the query; if nothing
    # overlaps and nothing is pinned, fall back to the most recent few.
    relevant = [
        i
        for i in ranked
        if i.pinned or (_tokens(i.text) & query_tokens)
    ]
    if not relevant:
        relevant = ranked[:limit]
    return relevant[:limit]


_KIND_LABELS = {
    MemoryKind.NOTE: "Note",
    MemoryKind.DECISION: "Decision",
    MemoryKind.CORRECTION: "Correction",
    MemoryKind.QA: "Earlier Q&A",
    MemoryKind.FACT: "Fact",
}


def format_memory_context(items: list[MemoryItem], max_chars: int = 1500) -> str:
    """A compact, labelled block of memory to prepend to a prompt."""
    if not items:
        return ""
    lines: list[str] = []
    used = 0
    for item in items:
        label = _KIND_LABELS.get(item.kind, "Note")
        text = " ".join(item.text.split())
        line = f"- {label}: {text}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line)
    if not lines:
        return ""
    return "Project memory the team has recorded (treat as authoritative):\n" + "\n".join(lines)
