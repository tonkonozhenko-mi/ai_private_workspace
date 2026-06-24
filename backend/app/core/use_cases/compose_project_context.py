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
from dataclasses import dataclass

from app.core.domain.project_graph import EntityType
from app.core.domain.project_memory import (
    MemoryItem,
    MemoryKind,
    format_memory_context,
    rank_memory_by_similarity,
    select_relevant_memory,
)
from app.core.domain.user_profile import (
    format_user_profile_context,
    select_for_prompt,
)
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort
from app.core.ports.user_profile_repository import UserProfileRepositoryPort

_WORD_RE = re.compile(r"[a-z0-9_]+")
_HANDBOOK_MAX = 1200
_TOTAL_MAX = 3500


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


class ComposeProjectContextUseCase:
    # Beyond this many recalled candidates, a semantic re-rank is worth its cost;
    # at or below it, keyword recall already returns everything we'd keep.
    _SEMANTIC_RERANK_MIN_CANDIDATES = 6
    _SEMANTIC_CANDIDATE_LIMIT = 12
    _SEMANTIC_EMBED_CHARS = 400

    def __init__(
        self,
        memory_repository: ProjectMemoryRepositoryPort,
        project_graph_repository: ProjectGraphRepositoryPort,
        user_profile_repository: UserProfileRepositoryPort | None = None,
        embedding_provider=None,
    ) -> None:
        self.memory_repository = memory_repository
        self.project_graph_repository = project_graph_repository
        # Optional so existing callers/tests keep working; when present, the
        # user's cross-project profile is applied to every answer.
        self.user_profile_repository = user_profile_repository
        # Optional: when present, recalled memory is re-ranked by embedding
        # similarity (catches synonyms/paraphrases keyword overlap misses). None
        # keeps the deterministic keyword + pin + recency behaviour unchanged.
        self.embedding_provider = embedding_provider

    def _select_memory(self, items: list[MemoryItem], query: str, limit: int) -> list[MemoryItem]:
        """Keyword recall, then an optional semantic re-rank of the candidates.

        Semantic re-rank is best-effort: skipped when there's no embedder or few
        candidates, and it falls back to the keyword order on any error, so memory
        selection can never fail an answer.
        """
        candidates = select_relevant_memory(items, query, limit=self._SEMANTIC_CANDIDATE_LIMIT)
        if (
            self.embedding_provider is None
            or len(candidates) <= max(limit, self._SEMANTIC_RERANK_MIN_CANDIDATES)
        ):
            return candidates[:limit]
        try:
            query_vec = self.embedding_provider.embed_text(query)
            item_vecs = [
                self.embedding_provider.embed_text(item.text[: self._SEMANTIC_EMBED_CHARS])
                for item in candidates
            ]
            return rank_memory_by_similarity(candidates, query_vec, item_vecs, limit=limit)
        except Exception:  # noqa: BLE001 - memory selection must never fail the answer
            return candidates[:limit]

    def compose(self, workspace_id: str, query: str) -> str:
        text, _ = self.compose_with_stats(workspace_id, query)
        return text

    def compose_with_stats(
        self, workspace_id: str, query: str
    ) -> tuple[str, "ProjectContextStats"]:
        blocks: list[str] = []

        # The user's cross-project profile comes first — it shapes how to answer
        # (tone, language, focus), before any project-specific knowledge.
        profile_count = 0
        if self.user_profile_repository is not None:
            profile_items = select_for_prompt(self.user_profile_repository.list(), query)
            profile_block = format_user_profile_context(profile_items)
            if profile_block:
                blocks.append(profile_block)
                profile_count = len(profile_items)

        items = self.memory_repository.list(workspace_id)
        handbook = next((i for i in items if i.kind == MemoryKind.HANDBOOK), None)
        has_handbook = handbook is not None
        if handbook:
            text = handbook.text.strip()
            if len(text) > _HANDBOOK_MAX:
                text = text[:_HANDBOOK_MAX] + " …"
            blocks.append("Project handbook (background):\n" + text)

        relevant = self._select_memory(items, query, limit=6)
        memory_block = format_memory_context(relevant)
        if memory_block:
            blocks.append(memory_block)

        graph_block, graph_count = self._graph_facts(workspace_id, query)
        if graph_block:
            blocks.append(graph_block)

        stats = ProjectContextStats(
            memory_items=len(relevant) if memory_block else 0,
            graph_facts=graph_count,
            handbook=has_handbook,
            profile_facts=profile_count,
        )
        if not blocks:
            return "", stats
        combined = "\n\n".join(blocks)
        if len(combined) > _TOTAL_MAX:
            combined = combined[:_TOTAL_MAX] + " …"
        return combined, stats

    # Convenience for callbacks that take (workspace_id, query) -> str.
    def __call__(self, workspace_id: str, query: str) -> str:
        return self.compose(workspace_id, query)

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
