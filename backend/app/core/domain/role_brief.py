"""Role-specific project brief and suggested questions — deterministic.

After a scan, a viewer should not land on one generic overview. They should see
a short brief framed for *their* role and a handful of questions worth asking —
but only questions the project can actually answer from its own evidence.

Both are derived from the role-neutral :class:`ProjectGraph` and the
:class:`RoleLens` (which already declares each role's priority entity types and
highlighted finding categories). No technology names are hardcoded: the brief
counts and names whatever entities of those *generic types* exist, and a
question is offered only when the matching evidence is present. No LLM here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.domain.project_graph import EntityType, ProjectGraph
from app.core.domain.role_lens import RoleLens

# Plain-language label for each generic entity type, for the brief's fact lines.
_ENTITY_LABEL: dict[str, str] = {
    EntityType.SERVICE: "Services",
    EntityType.ENVIRONMENT: "Environments",
    EntityType.PIPELINE: "Pipelines",
    EntityType.PIPELINE_JOB: "CI jobs",
    EntityType.INFRA_COMPONENT: "Infrastructure",
    EntityType.CONFIG_FILE: "Config files",
    EntityType.CONTAINER_IMAGE: "Container images",
    EntityType.APPLICATION: "Applications",
    EntityType.MODULE: "Modules",
    EntityType.DEPENDENCY: "Dependencies",
    EntityType.CLOUD_SERVICE: "Cloud services",
    EntityType.REFERENCE: "References",
}

# Each candidate question is gated by an entity type that must exist for the
# question to be answerable. Generic — phrased around the *kind* of thing, never
# a specific tool. ``topic`` ties the question to a graph type so it can be
# ordered by the role's own priorities.
@dataclass(frozen=True)
class _QuestionCandidate:
    question: str
    requires_type: str | None  # entity type that must be present (None = always)


_QUESTION_CANDIDATES: list[_QuestionCandidate] = [
    _QuestionCandidate("How is this project deployed, and to which environments?", EntityType.PIPELINE),
    _QuestionCandidate("What runs in CI on a push, a pull request, and a tag?", EntityType.PIPELINE),
    _QuestionCandidate("How do the environments differ from each other?", EntityType.ENVIRONMENT),
    _QuestionCandidate("What infrastructure does this project provision?", EntityType.INFRA_COMPONENT),
    _QuestionCandidate("Which cloud services does this project use?", EntityType.CLOUD_SERVICE),
    _QuestionCandidate("How is the application structured into modules?", EntityType.MODULE),
    _QuestionCandidate("What are the main services, and how do they fit together?", EntityType.SERVICE),
    _QuestionCandidate("Which third-party dependencies does this project rely on?", EntityType.DEPENDENCY),
    _QuestionCandidate("Where is configuration kept, and what shapes runtime behaviour?", EntityType.CONFIG_FILE),
    # These two are always worth offering — every project can answer them.
    _QuestionCandidate("Where should I start reading to understand this repo?", None),
    _QuestionCandidate("What are the biggest risks flagged here, and what should I check?", None),
]


@dataclass(frozen=True)
class BriefFact:
    label: str
    count: int
    examples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"label": self.label, "count": self.count, "examples": list(self.examples)}


@dataclass(frozen=True)
class RoleBrief:
    role: str
    label: str  # e.g. "DevOps"
    focus: str  # one plain-language line: what this role should care about here
    facts: list[BriefFact] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "label": self.label,
            "focus": self.focus,
            "facts": [f.as_dict() for f in self.facts],
            "top_risks": list(self.top_risks),
            "suggested_questions": list(self.suggested_questions),
        }


def _focus_line(lens: RoleLens, facts: list[BriefFact]) -> str:
    """A single honest line describing what this role's view emphasises."""
    present = [f.label.lower() for f in facts if f.count > 0]
    if not present:
        return (
            f"Viewed for {lens.label}. The scan did not detect much yet — "
            "build the map or scan a richer project to see more."
        )
    if len(present) == 1:
        emphasis = present[0]
    elif len(present) == 2:
        emphasis = f"{present[0]} and {present[1]}"
    else:
        emphasis = f"{', '.join(present[:-1])}, and {present[-1]}"
    return f"Viewed for {lens.label}: this dashboard leads with {emphasis}."


def build_role_brief(graph: ProjectGraph, lens: RoleLens, max_examples: int = 3) -> RoleBrief:
    """Compose a deterministic, role-focused brief from the project graph."""
    # Facts: one line per priority entity type the role cares about, but only
    # those actually present. Order follows the role's own priority list.
    facts: list[BriefFact] = []
    for entity_type in lens.priority_entity_types:
        entities = graph.entities_of_type(entity_type)
        if not entities:
            continue
        label = _ENTITY_LABEL.get(entity_type, entity_type.replace("_", " ").title())
        examples = [e.name for e in entities[:max_examples]]
        facts.append(BriefFact(label=label, count=len(entities), examples=examples))

    # Top risks: findings in the role's highlighted categories first, then any
    # remaining, highest severity first. Already review-oriented in the UI.
    severity_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    highlighted = set(lens.highlighted_finding_categories)

    def risk_key(f) -> tuple[int, int]:
        return (0 if f.category in highlighted else 1, severity_rank.get(f.severity, 9))

    top_risks = [f.title for f in sorted(graph.findings, key=risk_key)[:3]]

    return RoleBrief(
        role=lens.role,
        label=lens.label,
        focus=_focus_line(lens, facts),
        facts=facts,
        top_risks=top_risks,
        suggested_questions=suggested_questions(graph, lens),
    )


def suggested_questions(graph: ProjectGraph, lens: RoleLens, limit: int = 5) -> list[str]:
    """Questions worth asking — only those the project's evidence can answer,
    ordered by how central each topic is to this role."""
    present_types = {e.type for e in graph.entities}

    # Role relevance: a question about a priority type sorts first.
    priority_rank = {t: i for i, t in enumerate(lens.priority_entity_types)}

    # Split into the always-on orientation questions (no required type) and the
    # evidence-gated, role-relevant ones. The orientation questions are core for
    # every role, so they are guaranteed a slot; the role questions lead.
    general = [c for c in _QUESTION_CANDIDATES if c.requires_type is None]
    typed = [
        c
        for c in _QUESTION_CANDIDATES
        if c.requires_type is not None and c.requires_type in present_types
    ]

    def order_key(cand: _QuestionCandidate) -> tuple[int, int]:
        # Priority-typed questions first (by the role's own order), then the rest
        # in their declared order.
        if cand.requires_type in priority_rank:
            return (0, priority_rank[cand.requires_type])
        return (1, _QUESTION_CANDIDATES.index(cand))

    typed_ordered = sorted(typed, key=order_key)

    # Reserve slots for the general questions, fill the rest with role questions.
    role_slots = max(0, limit - len(general))
    chosen = typed_ordered[:role_slots] + general

    seen: set[str] = set()
    out: list[str] = []
    for cand in chosen:
        if cand.question not in seen:
            seen.add(cand.question)
            out.append(cand.question)
        if len(out) >= limit:
            break
    return out
