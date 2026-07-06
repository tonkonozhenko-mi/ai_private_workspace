"""Deterministic starter questions for the empty Ask composer (D1).

The blank composer is the first-session barrier: the user doesn't know what to
ask. This offers a few clickable questions built *deterministically* from the
project map — "How is this deployed?" only appears when a pipeline was found,
"How do the environments differ?" only when environments were — so every
suggestion is answerable from the project. Falls back to a generic starter set
before the map exists. No LLM.
"""

from __future__ import annotations

from app.core.domain.project_graph import ProjectGraph
from app.core.domain.role_brief import suggested_questions
from app.core.domain.role_lens import RoleLens

# Shown before a project map exists (or if the map yields nothing) — safe on any
# project, and each is genuinely answerable by retrieval/handbook.
GENERIC_STARTERS: tuple[str, ...] = (
    "What is this project about?",
    "How do I run this project locally?",
    "Where should I start reading the code?",
    "How is this project deployed?",
)


def starter_questions(
    graph: ProjectGraph | None,
    lens: RoleLens,
    limit: int = 4,
) -> list[str]:
    """Up to ``limit`` clickable starter questions. Map-derived and role-ordered
    when a graph exists; a generic starter set otherwise."""
    if graph is not None and graph.entities:
        questions = suggested_questions(graph, lens, limit=limit)
        if questions:
            return questions[:limit]
    return list(GENERIC_STARTERS[:limit])
