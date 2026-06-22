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
    MemoryKind,
    format_memory_context,
    select_relevant_memory,
)
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_memory_repository import ProjectMemoryRepositoryPort

_WORD_RE = re.compile(r"[a-z0-9_]+")
_HANDBOOK_MAX = 1200
_TOTAL_MAX = 3500


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall(text.lower()) if len(t) > 2}


@dataclass(frozen=True)
class ComposeProjectContextInput:
    workspace_id: str
    query: str


class ComposeProjectContextUseCase:
    def __init__(
        self,
        memory_repository: ProjectMemoryRepositoryPort,
        project_graph_repository: ProjectGraphRepositoryPort,
    ) -> None:
        self.memory_repository = memory_repository
        self.project_graph_repository = project_graph_repository

    def compose(self, workspace_id: str, query: str) -> str:
        blocks: list[str] = []

        items = self.memory_repository.list(workspace_id)
        handbook = next((i for i in items if i.kind == MemoryKind.HANDBOOK), None)
        if handbook:
            text = handbook.text.strip()
            if len(text) > _HANDBOOK_MAX:
                text = text[:_HANDBOOK_MAX] + " …"
            blocks.append("Project handbook (background):\n" + text)

        relevant = select_relevant_memory(items, query, limit=6)
        memory_block = format_memory_context(relevant)
        if memory_block:
            blocks.append(memory_block)

        graph_block = self._graph_facts(workspace_id, query)
        if graph_block:
            blocks.append(graph_block)

        if not blocks:
            return ""
        combined = "\n\n".join(blocks)
        if len(combined) > _TOTAL_MAX:
            combined = combined[:_TOTAL_MAX] + " …"
        return combined

    # Convenience for callbacks that take (workspace_id, query) -> str.
    def __call__(self, workspace_id: str, query: str) -> str:
        return self.compose(workspace_id, query)

    def _graph_facts(self, workspace_id: str, query: str) -> str:
        graph = self.project_graph_repository.get_latest_graph(workspace_id)
        if graph is None:
            return ""
        q = _tokens(query)
        if not q:
            return ""
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
            return ""
        lines = ["Relevant facts from the project map:"]
        for e in matched_entities:
            src = f" ({e.source_file})" if e.source_file else ""
            lines.append(f"- {e.name} [{e.type}]{src}")
        for f in matched_findings:
            lines.append(f"- risk: {f.title} [{f.severity}]")
        return "\n".join(lines)
