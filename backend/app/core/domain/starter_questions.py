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

# Before the map exists the questions cannot come from facts — but they can still
# come from the person. A tester opening a strange repository does not want to know
# where to start reading the code; they want to know what is risky to change and how
# to run the tests. Every question here is answerable from the files alone, so none
# of them promises something the index cannot deliver.
ROLE_STARTERS: dict[str, tuple[str, ...]] = {
    "developer": (
        "What is this project about?",
        "Where should I start reading the code?",
        "How do I run this project locally?",
        "How is the code structured?",
    ),
    "tester": (
        "How do I run the tests?",
        "What is risky to change here?",
        "Which parts of this project have no tests?",
        "What does the CI pipeline check?",
    ),
    "manager": (
        "What is this project about?",
        "What are the main risks in this project?",
        "What changed recently?",
        "How is this project deployed?",
    ),
    "devops": (
        "How is this project deployed?",
        "Which environments exist and how do they differ?",
        "What runs in CI and when?",
        "Where is the infrastructure defined?",
    ),
    "business_analyst": (
        "What does this system do for its users?",
        "What are the main entities and flows?",
        "Which integrations does it depend on?",
        "What is this project about?",
    ),
    "dba": (
        "What tables exist and how are they related?",
        "What do the migrations do, and in what order?",
        "Which tables have no primary key or no index on a foreign key?",
        "Where is the database configured?",
    ),
}


def starter_questions(
    graph: ProjectGraph | None,
    lens: RoleLens,
    limit: int = 4,
) -> list[str]:
    """Up to ``limit`` clickable starter questions. Map-derived and role-ordered
    when a graph exists; otherwise the role's own openers, and the generic set for a
    role we don't know."""
    if graph is not None and graph.entities:
        questions = suggested_questions(graph, lens, limit=limit)
        if questions:
            return questions[:limit]
    return list(ROLE_STARTERS.get(lens.role, GENERIC_STARTERS)[:limit])
