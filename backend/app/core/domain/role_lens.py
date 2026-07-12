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


# Until every role had facts of its own, all five lenses reordered the same DevOps
# entities: the tester's "priorities" were pipelines and environments, the analyst's
# were services. That is not a lens, it is a label. Each role now leads with the
# entities its own analyzer produced — modules for the developer, test suites for the
# tester, endpoints for the analyst, tables for the DBA — and the rest still follows.

_DEVELOPER = RoleLens(
    role="developer",
    label="Developer",
    priority_entity_types=[
        EntityType.APPLICATION,
        EntityType.MODULE,
        EntityType.DEPENDENCY,
        EntityType.SERVICE,
        EntityType.CONFIG_FILE,
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
        EntityType.TEST_SUITE,
        EntityType.MODULE,
        EntityType.PIPELINE_JOB,
        EntityType.API_ENDPOINT,
        EntityType.ENVIRONMENT,
    ],
    highlighted_finding_categories=[
        FindingCategory.TESTING,
        FindingCategory.RELIABILITY,
        FindingCategory.OBSERVABILITY,
    ],
    # Risks first, not Deployment: a tester's first question is what is likely to
    # break, not how it ships. Opening on Deployment made the tester's view look
    # like the DevOps view wearing a different name.
    section_order=[
        Section.SUMMARY,
        Section.RISKS,
        Section.DEPLOYMENT,
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
        EntityType.API_ENDPOINT,
        EntityType.DOMAIN_ENTITY,
        EntityType.TABLE,
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

_MANAGER = RoleLens(
    role="manager",
    label="Manager",
    priority_entity_types=[
        EntityType.APPLICATION,
        EntityType.SERVICE,
        EntityType.ENVIRONMENT,
        EntityType.PIPELINE,
    ],
    highlighted_finding_categories=[
        FindingCategory.SECURITY,
        FindingCategory.RELIABILITY,
        FindingCategory.DEPLOYMENT,
    ],
    section_order=[
        Section.SUMMARY,
        Section.RISKS,
        Section.ENVIRONMENTS,
        Section.DEPLOYMENT,
        Section.IMPORTANT_FILES,
        Section.INFRASTRUCTURE,
        Section.QUESTIONS,
    ],
)

# The five canonical roles, plus legacy assistant_modes folded onto the nearest
# one so older workspaces keep resolving. Documentation reads like a developer
# view; incident support like a DevOps view; the old "manager_summary" is the
# Manager role.
_DBA = RoleLens(
    role="dba",
    label="DBA",
    priority_entity_types=[
        EntityType.TABLE,
        EntityType.MIGRATION,
        EntityType.DOMAIN_ENTITY,
        EntityType.INFRA_COMPONENT,
        EntityType.SERVICE,
    ],
    highlighted_finding_categories=[
        FindingCategory.RELIABILITY,
        FindingCategory.SECURITY,
        FindingCategory.CONFIGURATION,
    ],
    section_order=[
        Section.SUMMARY,
        Section.RISKS,
        Section.IMPORTANT_FILES,
        Section.INFRASTRUCTURE,
        Section.ENVIRONMENTS,
        Section.DEPLOYMENT,
        Section.QUESTIONS,
    ],
)

# The roles a person can actually choose. Everything that offers a role — the
# create-project form, the Intelligence lens picker, Settings skills — must offer
# exactly these, and nothing may offer a role that has no lens here. DBA existed
# in the create form but not in the Intelligence picker, so a DBA workspace could
# not switch back to its own lens; one list, checked by a test, is the cure.
CANONICAL_ROLES: tuple[str, ...] = (
    "developer",
    "devops",
    "tester",
    "business_analyst",
    "manager",
    "dba",
)

ROLE_LENSES: dict[str, RoleLens] = {
    "developer": _DEVELOPER,
    "devops": _DEVOPS,
    "tester": _TESTER,
    "business_analyst": _BUSINESS_ANALYST,
    "manager": _MANAGER,
    "dba": _DBA,
    # Legacy / folded modes.
    "documentation": _DEVELOPER,
    "support_incident": _DEVOPS,
    "incident_support": _DEVOPS,
    "manager_summary": _MANAGER,
}


def role_lens_for(assistant_mode: str | None) -> RoleLens:
    """The lens for an assistant mode; unknown/empty modes fall back to Developer."""
    key = (assistant_mode or "").strip().lower()
    return ROLE_LENSES.get(key, _DEVELOPER)
