from typing import Protocol

from app.core.domain.skill_profile import WorkspaceSkillProfile


class SkillProfileRepositoryPort(Protocol):
    def get(self, workspace_id: str) -> WorkspaceSkillProfile | None:
        """Return saved workspace skill profile, if present."""

    def save(self, profile: WorkspaceSkillProfile) -> WorkspaceSkillProfile:
        """Persist workspace skill profile."""


SkillProfileRepository = SkillProfileRepositoryPort
