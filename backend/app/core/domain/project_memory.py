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
    # The "why is it built this way" layer: rationale behind a design choice, and
    # how a past incident was resolved. These are the highest-value memories — the
    # context that a new model (or a new teammate) otherwise cannot recover.
    ARCHITECTURE_DECISION = "architecture_decision"
    INCIDENT_SOLUTION = "incident_solution"
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
    relevant = [i for i in ranked if i.pinned or (_tokens(i.text) & query_tokens)]
    if not relevant:
        relevant = ranked[:limit]
    return relevant[:limit]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 for degenerate input."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_memory_by_similarity(
    items: list[MemoryItem],
    query_vec: list[float],
    item_vecs: list[list[float]],
    limit: int = 6,
) -> list[MemoryItem]:
    """Re-rank already-recalled memory by semantic similarity to the query.

    Pinned items always sort first (the user forced them in); the rest are ordered
    by cosine, so a question about "production" surfaces a memory that says "prod
    is called prd" even with no shared words. Pairs items with their precomputed
    embedding by position; the embedding is done by the caller (the domain stays
    free of any provider). Falls back to the input order if vectors are missing.
    """
    if not items or len(item_vecs) != len(items):
        return items[:limit]
    scored = [
        (1 if item.pinned else 0, cosine_similarity(query_vec, vec), index, item)
        for index, (item, vec) in enumerate(zip(items, item_vecs, strict=False))
    ]
    # Sort by (pinned, similarity) desc; index keeps it stable for ties.
    scored.sort(key=lambda t: (t[0], t[1], -t[2]), reverse=True)
    return [item for _pinned, _sim, _index, item in scored[:limit]]


def prior_qa_ids_for(items: list[MemoryItem], question: str) -> list[str]:
    """Ids of earlier auto-captured Q&A items for the same question.

    Used so re-asking a question replaces its previous auto-answer instead of
    piling up duplicates. Pinned Q&A are kept (the user deliberately saved them).
    """
    norm = " ".join(question.lower().split())
    out: list[str] = []
    for item in items:
        if item.kind != MemoryKind.QA or item.pinned:
            continue
        first_line = item.text.split("\n", 1)[0]
        recorded_q = first_line[2:].strip() if first_line[:2].lower() == "q:" else ""
        if " ".join(recorded_q.lower().split()) == norm:
            out.append(item.id)
    return out


_KIND_LABELS = {
    MemoryKind.NOTE: "Note",
    MemoryKind.DECISION: "Decision",
    MemoryKind.CORRECTION: "Correction",
    MemoryKind.QA: "Earlier Q&A",
    MemoryKind.FACT: "Fact",
    MemoryKind.ARCHITECTURE_DECISION: "Architecture decision (why)",
    MemoryKind.INCIDENT_SOLUTION: "Past incident fix",
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
