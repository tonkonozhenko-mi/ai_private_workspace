"""Role lenses for Project Intelligence.

A lens re-orders and prioritises the *same* role-neutral project graph for a
given role (DevOps / Developer / Tester / Business analyst …). It selects which
entity types and finding categories to surface first and in what section order.

A lens NEVER changes facts: "not detected" stays "not detected" for every role.
The role only steers emphasis and the LLM explanation framing (the prose hint is
already provided by ``rag_prompt.assistant_mode_lens_hint``).
"""

from dataclasses import dataclass, field

from app.core.domain.project_graph import EntityType, FindingCategory


class Section:
    SUMMARY = "summary"
    INFRASTRUCTURE = "infrastructure"
    DEPLOYMENT = "deployment"
    ENVIRONMENTS = "environments"
    RISKS = "risks"
    IMPORTANT_FILES = "important_files"
    QUESTIONS = "questions"


ALL_SECTIONS: list[str] = [
    Section.SUMMARY,
    Section.INFRASTRUCTURE,
    Section.DEPLOYMENT,
    Section.ENVIRONMENTS,
    Section.RISKS,
    Section.IMPORTANT_FILES,
    Section.QUESTIONS,
]


@dataclass(frozen=True)
class RoleLens:
    role: str
    label: str
    # Entity types to surface first (others still shown, lower in the list).
    priority_entity_types: list[str] = field(default_factory=list)
    # Finding categories to highlight for this role (others stay, de-emphasised).
    highlighted_finding_categories: list[str] = field(default_factory=list)
    # Section order for this role's view of Project Intelligence.
    section_order: list[str] = field(default_factory=lambda: list(ALL_SECTIONS))


_DEVELOPER = RoleLens(
    role="developer",
    label="Developer",
    priority_entity_types=[
        EntityType.SERVICE,
        EntityType.CONTAINER_IMAGE,
        EntityType.CONFIG_FILE,
        EntityType.PIPELINE,
    ],
    highlighted_finding_categories=[
        FindingCategory.CONFIGURATION,
        FindingCategory.RELIABILITY,
        FindingCategory.GENERAL,
    ],
    section_order=[
        Section.SUMMARY,
        Section.INFRASTRUCTURE,
        Section.IMPORTANT_FILES,
        Section.DEPLOYMENT,
        Section.RISKS,
        Section.ENVIRONMENTS,
        Section.QUESTIONS,
    ],
)

_DEVOPS = RoleLens(
    role="devops",
    label="DevOps",
    priority_entity_types=[
        EntityType.INFRA_COMPONENT,
        EntityType.ENVIRONMENT,
        EntityType.PIPELINE,
        EntityType.PIPELINE_JOB,
        EntityType.SERVICE,
    ],
    highlighted_finding_categories=[
        FindingCategory.SECURITY,
        FindingCategory.DEPLOYMENT,
        FindingCategory.RELIABILITY,
    ],
    section_order=[
        Section.SUMMARY,
        Section.INFRASTRUCTURE,
        Section.DEPLOYMENT,
        Section.ENVIRONMENTS,
        Section.RISKS,
        Section.IMPORTANT_FILES,
        Section.QUESTIONS,
    ],
)

_TESTER = RoleLens(
    role="tester",
    label="Tester / QA",
    priority_entity_types=[
        EntityType.PIPELINE,
        EntityType.PIPELINE_JOB,
        EntityType.ENVIRONMENT,
        EntityType.SERVICE,
    ],
    highlighted_finding_categories=[
        FindingCategory.TESTING,
        FindingCategory.RELIABILITY,
        FindingCategory.OBSERVABILITY,
    ],
    section_order=[
        Section.SUMMARY,
        Section.DEPLOYMENT,
        Section.RISKS,
        Section.ENVIRONMENTS,
        Section.INFRASTRUCTURE,
        Section.IMPORTANT_FILES,
        Section.QUESTIONS,
    ],
)

_BUSINESS_ANALYST = RoleLens(
    role="business_analyst",
    label="Business analyst",
    priority_entity_types=[
        EntityType.SERVICE,
        EntityType.ENVIRONMENT,
    ],
    highlighted_finding_categories=[
        FindingCategory.RELIABILITY,
        FindingCategory.DEPLOYMENT,
    ],
    section_order=[
        Section.SUMMARY,
        Section.ENVIRONMENTS,
        Section.RISKS,
        Section.DEPLOYMENT,
        Section.IMPORTANT_FILES,
        Section.INFRASTRUCTURE,
        Section.QUESTIONS,
    ],
)

# Registered lenses keyed by assistant_mode. Modes without a dedicated lens map
# to the nearest sensible one, mirroring assistant_mode_lens_hint's fallbacks.
ROLE_LENSES: dict[str, RoleLens] = {
    "developer": _DEVELOPER,
    "devops": _DEVOPS,
    "tester": _TESTER,
    "business_analyst": _BUSINESS_ANALYST,
    "documentation": _DEVELOPER,
    "support_incident": _DEVOPS,
    "manager_summary": _BUSINESS_ANALYST,
}


def role_lens_for(assistant_mode: str | None) -> RoleLens:
    """The lens for an assistant mode; unknown/empty modes fall back to Developer."""
    key = (assistant_mode or "").strip().lower()
    return ROLE_LENSES.get(key, _DEVELOPER)
