from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.domain.role_lens import CANONICAL_ROLES

DEFAULT_SKILL_PROFILE_NAME = "workspace"
DEFAULT_SKILL_IDS: tuple[str, ...] = ("devops",)

# The saveable skills ARE the canonical roles — the same six the create-project
# form, the Settings toggles and the Intelligence lens picker offer. This used
# to be a second, older vocabulary (documentation / incident_support /
# manager_summary), and the mismatch is what "skills don't save" was: the UI
# sent six roles, four of them were not in this list, and the ones that were not
# recognised were dropped without a word. Turning on Tester and pressing Save
# stored a profile with nothing enabled; reopening Settings showed DevOps again,
# because a role the server never returned fell back to its default. Nothing
# errored anywhere — the toggle simply would not stay.
#
# So there is one list now, taken from the one place that already defines it,
# and a test pins the two together.
KNOWN_SKILL_IDS: tuple[str, ...] = CANONICAL_ROLES

DEFAULT_SKILL_INSTRUCTIONS: dict[str, str] = {
    "developer": "Answer as a developer assistant. Focus on source code structure, implementation details, dependencies, tests, change impact, and practical next steps.",
    "devops": "Answer as a DevOps/platform assistant. Pay attention to infrastructure, CI/CD, Terraform, Terragrunt, Kubernetes, Docker, Helm, Jenkins pipelines, GitHub Actions, GitLab CI, runtime configuration, and deployment risks.",
    "tester": "Answer as a QA / test engineer. Focus on test coverage and test types, the critical flows to verify, regression-risk areas, edge cases, and what to test after a change.",
    "business_analyst": "Answer as a business analyst. Explain in plain language what the system does, its main entities and user flows, integrations, business rules, and the open questions worth clarifying.",
    "manager": "Answer for an engineering manager. Focus on a concise executive summary, project health, the main risks, recent changes, ownership, delivery flow, and stakeholder-friendly wording.",
    "dba": "Answer as a database engineer. Focus on the data model — tables, columns, primary and foreign keys, indexes, views — on migrations and the order they apply in, and on the schema-level risks worth checking. State findings as facts to verify, not verdicts.",
}

# Ids written by earlier versions, folded into the role they became rather than
# discarded. Someone who wrote their own guidance under "manager_summary" keeps
# it; it now lives on the Manager toggle. Mirrors the legacy entries in
# ROLE_LENSES, which fold the same way.
LEGACY_SKILL_IDS: dict[str, str] = {
    "documentation": "developer",
    "incident_support": "devops",
    "support_incident": "devops",
    "manager_summary": "manager",
}

# What one skill's guidance may say. The Settings textareas stop at exactly this
# many characters, so the limit is something you watch happen rather than
# something that quietly eats the end of your sentence after you press Save.
MAX_SKILL_INSTRUCTIONS_LENGTH = 1200

# How many skills' guidance may reach the prompt at once. Every role can be
# switched on together, so the bound is the number of roles — a smaller number
# would drop somebody's guidance without saying so, which is how a literal 5,
# left over from when there were five roles, became a bug the day DBA arrived.
MAX_ACTIVE_SKILL_INSTRUCTIONS = len(KNOWN_SKILL_IDS)


@dataclass(frozen=True)
class SkillProfileItem:
    id: str
    name: str
    enabled: bool
    custom_instructions: str


@dataclass(frozen=True)
class WorkspaceSkillProfile:
    workspace_id: str
    profile: str = DEFAULT_SKILL_PROFILE_NAME
    skills: tuple[SkillProfileItem, ...] = ()
    updated_at: str | None = None

    @property
    def enabled_skills(self) -> tuple[SkillProfileItem, ...]:
        return tuple(skill for skill in self.skills if skill.enabled)

    @property
    def enabled_skills_count(self) -> int:
        return len(self.enabled_skills)


def canonical_skill_id(skill_id: str) -> str | None:
    """The canonical role this id refers to, or None if it names no role at all."""
    key = (skill_id or "").strip().lower()
    if key in KNOWN_SKILL_IDS:
        return key
    return LEGACY_SKILL_IDS.get(key)


def default_skill_profile(workspace_id: str) -> WorkspaceSkillProfile:
    return WorkspaceSkillProfile(
        workspace_id=workspace_id,
        skills=tuple(
            SkillProfileItem(
                id=skill_id,
                name=_default_skill_name(skill_id),
                enabled=skill_id in DEFAULT_SKILL_IDS,
                custom_instructions=DEFAULT_SKILL_INSTRUCTIONS[skill_id],
            )
            for skill_id in KNOWN_SKILL_IDS
        ),
        updated_at=datetime.now(UTC).isoformat(),
    )


def normalize_skill_profile(
    workspace_id: str,
    profile: str,
    skills: list[SkillProfileItem] | tuple[SkillProfileItem, ...],
    updated_at: str | None = None,
) -> WorkspaceSkillProfile:
    """Bring a submitted profile to the canonical six roles.

    Legacy ids fold into the role they became; an id that names no role is not
    something this can honour, so callers that care are expected to check with
    ``canonical_skill_id`` and say so. What must never happen again is what used
    to: a recognisable role quietly discarded, and a Save that changed nothing.
    """
    incoming: dict[str, SkillProfileItem] = {}
    for skill in skills:
        canonical = canonical_skill_id(skill.id)
        if canonical is not None:
            # First wins, so a legacy duplicate cannot overwrite the current id.
            incoming.setdefault(canonical, skill)

    normalized: list[SkillProfileItem] = []
    for skill_id in KNOWN_SKILL_IDS:
        item = incoming.get(skill_id)
        normalized.append(
            SkillProfileItem(
                id=skill_id,
                name=(item.name if item and item.name.strip() else _default_skill_name(skill_id)),
                enabled=bool(item.enabled) if item is not None else skill_id in DEFAULT_SKILL_IDS,
                custom_instructions=(
                    item.custom_instructions.strip()[:MAX_SKILL_INSTRUCTIONS_LENGTH]
                    if item is not None and item.custom_instructions.strip()
                    else DEFAULT_SKILL_INSTRUCTIONS[skill_id]
                ),
            )
        )
    return WorkspaceSkillProfile(
        workspace_id=workspace_id,
        profile=profile.strip()[:80] or DEFAULT_SKILL_PROFILE_NAME,
        skills=tuple(normalized),
        updated_at=updated_at,
    )


def _default_skill_name(skill_id: str) -> str:
    return {
        "developer": "Developer",
        "devops": "DevOps",
        "tester": "Tester / QA",
        "business_analyst": "Business analyst",
        "manager": "Manager",
        "dba": "DBA",
    }.get(skill_id, skill_id.replace("_", " ").title())
