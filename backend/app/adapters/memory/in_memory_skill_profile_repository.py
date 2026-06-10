from datetime import UTC, datetime

from app.core.domain.skill_profile import WorkspaceSkillProfile, normalize_skill_profile


class InMemorySkillProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, WorkspaceSkillProfile] = {}

    def get(self, workspace_id: str) -> WorkspaceSkillProfile | None:
        return self._profiles.get(workspace_id)

    def save(self, profile: WorkspaceSkillProfile) -> WorkspaceSkillProfile:
        saved = normalize_skill_profile(
            workspace_id=profile.workspace_id,
            profile=profile.profile,
            skills=profile.skills,
            updated_at=profile.updated_at or datetime.now(UTC).isoformat(),
        )
        self._profiles[saved.workspace_id] = saved
        return saved
