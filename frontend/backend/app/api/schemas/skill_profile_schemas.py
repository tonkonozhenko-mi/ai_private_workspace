from pydantic import BaseModel, Field

from app.core.domain.skill_profile import SkillProfileItem, WorkspaceSkillProfile


class SkillProfileItemRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = False
    custom_instructions: str = Field(..., min_length=1, max_length=1200)


class WorkspaceSkillProfileRequest(BaseModel):
    profile: str = Field(default="workspace", min_length=1, max_length=80)
    skills: list[SkillProfileItemRequest] = Field(default_factory=list, max_length=5)


class SkillProfileItemResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    custom_instructions: str


class WorkspaceSkillProfileResponse(BaseModel):
    workspace_id: str
    profile: str
    skills: list[SkillProfileItemResponse]
    enabled_skills_count: int
    updated_at: str | None = None
    source: str


def to_skill_profile_item(item: SkillProfileItemRequest) -> SkillProfileItem:
    return SkillProfileItem(
        id=item.id,
        name=item.name,
        enabled=item.enabled,
        custom_instructions=item.custom_instructions,
    )


def to_workspace_skill_profile_response(
    profile: WorkspaceSkillProfile,
    *,
    source: str,
) -> WorkspaceSkillProfileResponse:
    return WorkspaceSkillProfileResponse(
        workspace_id=profile.workspace_id,
        profile=profile.profile,
        skills=[
            SkillProfileItemResponse(
                id=skill.id,
                name=skill.name,
                enabled=skill.enabled,
                custom_instructions=skill.custom_instructions,
            )
            for skill in profile.skills
        ],
        enabled_skills_count=profile.enabled_skills_count,
        updated_at=profile.updated_at,
        source=source,
    )
