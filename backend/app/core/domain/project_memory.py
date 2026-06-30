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
from datetime import datetime, timezone


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


class MemoryStatus:
    ACTIVE = "active"
    # Superseded / no longer true. Kept in the store (and visible in the UI) for
    # history, but never injected into prompts — stale memory poisons answers.
    OBSOLETE = "obsolete"


# Recency half-life: a memory this many days old counts half as much in ranking
# (unless pinned). Gentle, so old-but-relevant facts still surface; recent ones win ties.
_FRESHNESS_HALF_LIFE_DAYS = 90.0
# How much a "stale" memory (a file it references just changed) is down-weighted.
# It is NOT excluded — it may well still be true — only ranked lower until the
# user confirms or edits it. Pinned items are never penalised.
_STALE_PENALTY = 0.5


@dataclass(frozen=True)
class MemoryItem:
    id: str
    workspace_id: str
    kind: str
    text: str
    source: str
    created_at: str  # ISO 8601
    pinned: bool = False
    # Lifecycle: how sure we are it is still true, and whether it is current.
    confidence: float = 1.0  # 0.0–1.0; scales how strongly it is recalled
    status: str = MemoryStatus.ACTIVE
    updated_at: str | None = None  # set when status/confidence last changed
    # Auto-suspected stale: a file this memory references changed recently. Still
    # recalled (it may be true), but down-weighted and flagged for the user.
    stale: bool = False


_WORD_RE = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2}


def _parse_iso(timestamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _freshness_factor(item: MemoryItem, now: datetime) -> float:
    """Recency weight in (0, 1]: ~1.0 when fresh, 0.5 at one half-life old.

    Pinned items don't decay (the user forced them in); an unparseable timestamp
    counts as fully fresh so a bad date never silently drops a memory.
    """
    if item.pinned:
        return 1.0
    created = _parse_iso(item.created_at)
    if created is None:
        return 1.0
    age_days = max(0.0, (now - created).total_seconds() / 86400.0)
    return _FRESHNESS_HALF_LIFE_DAYS / (_FRESHNESS_HALF_LIFE_DAYS + age_days)


def select_relevant_memory(
    items: list[MemoryItem],
    query: str,
    limit: int = 6,
    now: datetime | None = None,
) -> list[MemoryItem]:
    """Rank memory for a query: pinned first, then keyword overlap weighted by
    confidence and recency.

    Obsolete items are excluded entirely (stale memory must never reach a prompt),
    as is the handbook (the context composer handles it separately). Among the
    rest, the keyword-overlap score is scaled by the item's ``confidence`` and a
    recency factor, so a confident, recent note outranks an old, uncertain one.
    """
    now = now or datetime.now(timezone.utc)
    query_tokens = _tokens(query)
    candidates = [
        i for i in items if i.kind != MemoryKind.HANDBOOK and i.status != MemoryStatus.OBSOLETE
    ]

    def score(item: MemoryItem) -> tuple:
        overlap = len(_tokens(item.text) & query_tokens)
        stale_factor = _STALE_PENALTY if (item.stale and not item.pinned) else 1.0
        weighted = overlap * max(0.0, item.confidence) * _freshness_factor(item, now) * stale_factor
        return (1 if item.pinned else 0, weighted, item.created_at)

    ranked = sorted(candidates, key=score, reverse=True)
    # Keep items that are pinned or actually overlap the query; if nothing
    # overlaps and nothing is pinned, fall back to the most recent few.
    relevant = [i for i in ranked if i.pinned or (_tokens(i.text) & query_tokens)]
    if not relevant:
        relevant = ranked[:limit]
    return relevant[:limit]


def memories_referencing_paths(items: list[MemoryItem], changed_paths: list[str]) -> list[str]:
    """Ids of active, non-handbook memories whose text references one of the
    ``changed_paths`` (by full path or its basename-with-extension).

    Used to flag memory as "stale, please review" when the Watcher sees those
    files change. Deterministic; requires a basename with an extension (e.g.
    ``main.tf``) so ordinary prose words can't trip it. Pinned items are still
    flagged (the user is shown the hint) but they keep their ranking weight.
    """
    if not changed_paths:
        return []
    targets: set[str] = set()
    for path in changed_paths:
        clean = (path or "").strip().strip("/").lower()
        if not clean:
            continue
        targets.add(clean)
        base = clean.split("/")[-1]
        if "." in base and len(base) >= 4:
            targets.add(base)
    if not targets:
        return []
    out: list[str] = []
    for item in items:
        if item.kind == MemoryKind.HANDBOOK or item.status == MemoryStatus.OBSOLETE:
            continue
        low = item.text.lower()
        if any(target in low for target in targets):
            out.append(item.id)
    return out


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
