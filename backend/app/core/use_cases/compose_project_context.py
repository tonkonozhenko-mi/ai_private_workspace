"""Compose the shared project-context block injected into any LLM call.

This is the single place that turns the project's durable knowledge into prompt
context, so Ask, the Investigator and the overview all benefit identically. It
combines, in order and bounded by size:

1. the project handbook (a distilled summary), trimmed;
2. the most relevant memory items (pinned + keyword + recency);
3. a few graph facts that match the question.

Everything is deterministic and local. Returns ``""`` when there is nothing.
"""

import re
from dataclasses import dataclass, field

from app.core.domain.project_graph import EntityType
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    MemoryStatus,
    cosine_similarity,
    format_guardrails,
    format_memory_context,
    rank_memory_by_similarity,
    select_relevant_memory,
)
from app.core.domain.user_profile import (
    answer_style_directive,
    format_user_profile_context,
    select_for_prompt,
)
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort
from app.core.ports.project_watch_repository import ProjectWatchRepositoryPort
from app.core.ports.user_profile_repository import UserProfileRepositoryPort

_WORD_RE = re.compile(r"[a-z0-9_]+")


@dataclass(frozen=True)
class ContextBudget:
    """One explicit place that allocates the prompt's context window across the
    durable sources, in characters (a stable proxy for tokens that needs no
    tokenizer). Every section is trimmed to its own cap, and the assembled block
    to ``total`` — so no single source (a long handbook, a chatty note) can crowd
    out the retrieved code the answer actually needs.

    ``handbook_small`` is what's *always* injected as background; ``handbook_full``
    is the larger cap used only when the question is about the project as a whole
    (see ``_handbook_block``), so the handbook informs without dominating.
    """

    profile: int = 400
    handbook_small: int = 500
    handbook_full: int = 1200
    memory: int = 1500
    guardrails: int = 700
    graph: int = 600
    changes: int = 700
    total: int = 3500


DEFAULT_BUDGET = ContextBudget()


def _trim(text: str, max_chars: int) -> str:
    text = text.rstrip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " …"


def _shorten(text: str, max_chars: int = 140) -> str:
    """One-line, length-capped version of a note, for the 'Why this answer?' list."""
    one_line = " ".join((text or "").split())
    return one_line if len(one_line) <= max_chars else one_line[:max_chars].rstrip() + "…"


def _handbook_block(handbook_text: str, query: str, budget: ContextBudget) -> str:
    """The handbook, tiered: a short digest always, the fuller text only when the
    question is broad/project-wide.

    A small digest (first paragraph, capped at ``handbook_small``) is cheap and
    keeps every answer grounded in *this* project. The fuller handbook is added
    only when the query meaningfully overlaps it — i.e. the user is asking about
    the project at large, not a single file — so it never crowds out retrieved
    code on a narrow question. Deterministic: overlap is token-based, no model.
    """
    text = (handbook_text or "").strip()
    if not text:
        return ""
    overlap = len(_tokens(query) & _tokens(text))
    cap = budget.handbook_full if overlap >= 3 else budget.handbook_small
    if len(text) <= cap:
        body = text
    elif cap == budget.handbook_small:
        # Prefer a clean cut at the first paragraph for the always-on digest.
        first_para = text.split("\n\n", 1)[0].strip()
        body = first_para if first_para and len(first_para) <= cap else _trim(text, cap)
    else:
        body = _trim(text, cap)
    return "Project handbook (background):\n" + body


# Words that signal the question is about recent change ("what changed today?",
# "що змінилось", "что нового со вчера"). When any appears, the dated change
# journal is added to the context so plain Ask can answer it. Kept multilingual
# (en/uk/ru) because the product is used in those languages.
_CHANGE_INTENT = (
    "chang",
    "what's new",
    "whats new",
    "recent",
    "latest",
    "today",
    "yesterday",
    "since",
    "updat",
    "modif",
    "diff",
    "new in",
    "змін",
    "сьогодн",
    "вчора",
    "останн",
    "новог",
    "онов",
    "недавн",
    "измен",
    "сегодн",
    "вчера",
    "нового",
)


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2}


@dataclass(frozen=True)
class ComposeProjectContextInput:
    workspace_id: str
    query: str


@dataclass(frozen=True)
class ProjectContextStats:
    """How much durable context an answer actually drew on."""

    memory_items: int = 0
    graph_facts: int = 0
    handbook: bool = False
    profile_facts: int = 0
    recent_changes: int = 0
    guardrails: int = 0
    # A short imperative reminder of the person's style/language preferences, to be
    # restated at the very end of the answer prompt (empty when they have none).
    style_directive: str = ""
    # For a "Why this answer?" panel: the notes/guardrails that actually went into
    # the prompt. Each item is {kind, text, grounding}. Kept short and optional so
    # the UI can show provenance on demand instead of crowding the answer.
    memory_used: list = field(default_factory=list)
    guardrails_used: list = field(default_factory=list)
    # The About-you facts that went into the prompt (each {category, text}), so the
    # "Why this answer?" panel can show the profile was actually applied.
    profile_used: list = field(default_factory=list)


class ComposeProjectContextUseCase:
    # Beyond this many recalled candidates, a semantic re-rank is worth its cost;
    # at or below it, keyword recall already returns everything we'd keep.
    _SEMANTIC_CANDIDATE_LIMIT = 12
    _SEMANTIC_EMBED_CHARS = 400
    # Cap how many notes we embed per query, so a large memory store stays cheap.
    # Memory is usually a handful of notes, so this rarely bites.
    _MAX_EMBED_ITEMS = 60
    # Floor on cosine similarity for a note to enter as a *semantic* candidate.
    # Guards against weak embedders dragging in unrelated notes (semantic noise);
    # keyword candidates are kept regardless, since they have lexical grounding.
    _SEMANTIC_MIN_SIM = 0.25

    def __init__(
        self,
        memory_repository: ProjectMemoryRepositoryPort,
        project_graph_repository: ProjectGraphRepositoryPort,
        user_profile_repository: UserProfileRepositoryPort | None = None,
        embedding_provider=None,
        watch_repository: ProjectWatchRepositoryPort | None = None,
        budget: ContextBudget | None = None,
    ) -> None:
        self.memory_repository = memory_repository
        self.project_graph_repository = project_graph_repository
        # Single explicit allocation of the context window across sources.
        self.budget = budget or DEFAULT_BUDGET
        # Optional so existing callers/tests keep working; when present, the
        # user's cross-project profile is applied to every answer.
        self.user_profile_repository = user_profile_repository
        # Optional: the dated change journal (git-based). When the question is
        # about recent changes, a compact recap is added so plain Ask can answer
        # "what changed today / since yesterday".
        self.watch_repository = watch_repository
        # Optional: when present, recalled memory is re-ranked by embedding
        # similarity (catches synonyms/paraphrases keyword overlap misses). None
        # keeps the deterministic keyword + pin + recency behaviour unchanged.
        self.embedding_provider = embedding_provider

    def _select_memory(self, items: list[MemoryItem], query: str, limit: int) -> list[MemoryItem]:
        """Parallel retrieval: keyword candidates ∪ semantic candidates, re-ranked.

        Keyword recall alone misses a note that means the same thing in different
        words (no shared tokens → never a candidate). So when an embedder is
        present we *also* pull the top semantic matches over the eligible notes and
        union them with the keyword hits before re-ranking by similarity. Without an
        embedder it stays pure keyword + pin + recency. Best-effort: any error or a
        missing embedder falls back to the keyword order, so selection never fails
        an answer.
        """
        keyword_candidates = select_relevant_memory(
            items, query, limit=self._SEMANTIC_CANDIDATE_LIMIT
        )
        if self.embedding_provider is None:
            return keyword_candidates[:limit]
        try:
            # Everything that could ever be recalled (active, non-handbook, non-
            # guardrail — those are injected separately and always).
            eligible = [
                i
                for i in items
                if i.kind not in (MemoryKind.HANDBOOK, MemoryKind.GUARDRAIL)
                and i.status != MemoryStatus.OBSOLETE
            ][: self._MAX_EMBED_ITEMS]
            if not eligible:
                return keyword_candidates[:limit]
            query_vec = self.embedding_provider.embed_text(query)
            vec_by_id = {
                it.id: self.embedding_provider.embed_text(it.text[: self._SEMANTIC_EMBED_CHARS])
                for it in eligible
            }
            # Only notes clearing the similarity floor are semantic candidates, so
            # a weak embedder can't drag in unrelated notes (semantic noise).
            scored = sorted(
                ((cosine_similarity(query_vec, vec_by_id[it.id]), it) for it in eligible),
                key=lambda pair: pair[0],
                reverse=True,
            )
            semantic_candidates = [it for sim, it in scored if sim >= self._SEMANTIC_MIN_SIM][
                : self._SEMANTIC_CANDIDATE_LIMIT
            ]
            # Union (dedup by id), keyword first so it's stable when scores tie.
            union: dict[str, MemoryItem] = {}
            for it in keyword_candidates + semantic_candidates:
                union.setdefault(it.id, it)
            union_items = list(union.values())
            union_vecs = [
                vec_by_id.get(it.id)
                or self.embedding_provider.embed_text(it.text[: self._SEMANTIC_EMBED_CHARS])
                for it in union_items
            ]
            return rank_memory_by_similarity(union_items, query_vec, union_vecs, limit=limit)
        except Exception:  # noqa: BLE001 - memory selection must never fail the answer
            return keyword_candidates[:limit]

    def compose(self, workspace_id: str, query: str) -> str:
        text, _ = self.compose_with_stats(workspace_id, query)
        return text

    def user_style_directive(self) -> str:
        """The person's style/language preference on its own, for prompts that skip
        retrieval (chit-chat). Cheap and best-effort: reads the profile only, no
        memory/graph work — so general conversation is still answered in the
        requested language without paying for a full context compose."""
        if self.user_profile_repository is None:
            return ""
        try:
            items = select_for_prompt(self.user_profile_repository.list(), "")
            return answer_style_directive(items)
        except Exception:  # noqa: BLE001 - never fail an answer over a preference
            return ""

    def compose_with_stats(
        self, workspace_id: str, query: str
    ) -> tuple[str, "ProjectContextStats"]:
        blocks: list[str] = []

        # The user's cross-project profile comes first — it shapes how to answer
        # (tone, language, focus), before any project-specific knowledge.
        profile_count = 0
        profile_used: list = []
        style_directive = ""
        if self.user_profile_repository is not None:
            profile_items = select_for_prompt(self.user_profile_repository.list(), query)
            profile_block = format_user_profile_context(profile_items)
            if profile_block:
                blocks.append(_trim(profile_block, self.budget.profile))
                profile_count = len(profile_items)
                # For the "Why this answer?" panel: the exact About-you facts that
                # went into the prompt, so the user can see the profile was applied.
                profile_used = [
                    {"category": i.category, "text": _shorten(i.text)} for i in profile_items
                ]
            # Restated separately at the very end of the answer prompt (strongest
            # position) so a small model actually applies the requested language.
            style_directive = answer_style_directive(profile_items)

        items = self.memory_repository.list(workspace_id)
        handbook = next((i for i in items if i.kind == MemoryKind.HANDBOOK), None)
        has_handbook = handbook is not None
        if handbook:
            handbook_block = _handbook_block(handbook.text, query, self.budget)
            if handbook_block:
                blocks.append(handbook_block)

        relevant = self._select_memory(items, query, limit=6)
        memory_block = format_memory_context(relevant, max_chars=self.budget.memory)
        if memory_block:
            blocks.append(memory_block)

        # Guardrails (negative memory) are constraints, not facts — injected on
        # every answer regardless of overlap, so a rule always applies.
        guardrails_block = format_guardrails(items, max_chars=self.budget.guardrails)
        guardrails_count = 0
        guardrails_used: list = []
        if guardrails_block:
            blocks.append(guardrails_block)
            active_rails = [
                i
                for i in items
                if i.kind == MemoryKind.GUARDRAIL and i.status != MemoryStatus.OBSOLETE
            ]
            guardrails_count = len(active_rails)
            guardrails_used = [_shorten(i.text) for i in active_rails]

        graph_block, graph_count = self._graph_facts(workspace_id, query)
        if graph_block:
            blocks.append(_trim(graph_block, self.budget.graph))

        changes_block, changes_count = self._recent_changes(workspace_id, query)
        if changes_block:
            blocks.append(changes_block)

        memory_used = (
            [
                {
                    "kind": i.kind,
                    "text": _shorten(i.text),
                    "grounding": getattr(i, "grounding", None),
                }
                for i in relevant
            ]
            if memory_block
            else []
        )
        stats = ProjectContextStats(
            memory_items=len(relevant) if memory_block else 0,
            graph_facts=graph_count,
            handbook=has_handbook,
            profile_facts=profile_count,
            recent_changes=changes_count,
            guardrails=guardrails_count,
            memory_used=memory_used,
            guardrails_used=guardrails_used,
            profile_used=profile_used,
            style_directive=style_directive,
        )
        if not blocks:
            return "", stats
        combined = "\n\n".join(blocks)
        if len(combined) > self.budget.total:
            combined = combined[: self.budget.total] + " …"
        return combined, stats

    # Convenience for callbacks that take (workspace_id, query) -> str.
    def __call__(self, workspace_id: str, query: str) -> str:
        return self.compose(workspace_id, query)

    def _recent_changes(self, workspace_id: str, query: str) -> tuple[str, int]:
        """A compact recap of the dated change journal, added only when the
        question is about recent changes. Lets plain Ask answer "what changed
        today / since yesterday" from the same git journal shown in History."""
        if self.watch_repository is None:
            return "", 0
        lowered = (query or "").lower()
        if not any(token in lowered for token in _CHANGE_INTENT):
            return "", 0
        try:
            entries = self.watch_repository.list_history(workspace_id, limit=5)
        except Exception:  # noqa: BLE001 - context is best-effort
            return "", 0
        if not entries:
            return "", 0

        lines = ["Recent project changes (dated change journal):"]
        used = 0
        for entry in entries:
            when = str(entry.get("checked_at") or entry.get("created_at") or "")[:10]
            recap = str(entry.get("llm_summary") or entry.get("summary") or "").strip()
            subjects = [s for s in (entry.get("commit_subjects") or []) if s][:4]
            line = f"- {when}: {recap}" if when else f"- {recap}"
            if subjects:
                line += " | commits: " + "; ".join(subjects)
            lines.append(line)
            used += 1
            if sum(len(item) for item in lines) > self.budget.changes:
                break
        block = _trim("\n".join(lines), self.budget.changes)
        return block, used

    def _graph_facts(self, workspace_id: str, query: str) -> tuple[str, int]:
        graph = self.project_graph_repository.get_latest_graph(workspace_id)
        if graph is None:
            return "", 0
        q = _tokens(query)
        if not q:
            return "", 0
        matched_entities = [
            e
            for e in graph.entities
            if e.type
            in (
                EntityType.SERVICE,
                EntityType.ENVIRONMENT,
                EntityType.INFRA_COMPONENT,
                EntityType.CLOUD_SERVICE,
                EntityType.PIPELINE,
                EntityType.APPLICATION,
            )
            and (_tokens(e.name) & q)
        ][:8]
        matched_findings = [f for f in graph.findings if _tokens(f.title) & q][:4]
        if not matched_entities and not matched_findings:
            return "", 0
        lines = ["Relevant facts from the project map:"]
        for e in matched_entities:
            src = f" ({e.source_file})" if e.source_file else ""
            lines.append(f"- {e.name} [{e.type}]{src}")
        for f in matched_findings:
            lines.append(f"- risk: {f.title} [{f.severity}]")
        return "\n".join(lines), len(matched_entities) + len(matched_findings)
