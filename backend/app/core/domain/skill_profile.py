from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_SKILL_PROFILE_NAME = "workspace"
DEFAULT_SKILL_IDS: tuple[str, ...] = ("devops",)
DEFAULT_SKILL_INSTRUCTIONS: dict[str, str] = {
    "devops": "Answer as a DevOps/platform assistant. Pay attention to infrastructure, CI/CD, Terraform, Terragrunt, Kubernetes, Docker, Helm, Jenkins pipelines, GitHub Actions, GitLab CI, runtime configuration, and deployment risks.",
    "developer": "Answer as a developer assistant. Focus on source code structure, implementation details, dependencies, tests, change impact, and practical next steps.",
    "documentation": "Answer as a documentation assistant. Focus on clear explanations, onboarding quality, README gaps, architecture notes, and concise project summaries.",
    "incident_support": "Answer as an incident support assistant. Focus on symptoms, likely causes, operational checks, logs, rollback risks, and step-by-step troubleshooting.",
    "manager_summary": "Answer as a manager-summary assistant. Focus on concise summaries, risks, progress, decisions, business impact, and stakeholder-friendly wording.",
}
KNOWN_SKILL_IDS: tuple[str, ...] = tuple(DEFAULT_SKILL_INSTRUCTIONS.keys())


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
    incoming = {skill.id: skill for skill in skills if skill.id in KNOWN_SKILL_IDS}
    normalized: list[SkillProfileItem] = []
    for skill_id in KNOWN_SKILL_IDS:
        item = incoming.get(skill_id)
        normalized.append(
            SkillProfileItem(
                id=skill_id,
                name=(item.name if item and item.name.strip() else _default_skill_name(skill_id)),
                enabled=bool(item.enabled) if item is not None else skill_id in DEFAULT_SKILL_IDS,
                custom_instructions=(
                    item.custom_instructions.strip()[:1200]
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
        "devops": "DevOps",
        "developer": "Developer",
        "documentation": "Documentation",
        "incident_support": "Incident Support",
        "manager_summary": "Manager Summary",
    }.get(skill_id, skill_id.replace("_", " ").title())
