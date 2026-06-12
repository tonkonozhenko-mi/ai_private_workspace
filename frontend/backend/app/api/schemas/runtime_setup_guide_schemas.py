from pydantic import BaseModel, Field

from app.core.domain.runtime_setup_guide import RuntimeSetupAction, RuntimeSetupGuide


class GetRuntimeSetupGuideRequest(BaseModel):
    assistant_profile_id: str = Field(..., min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    privacy_mode: str = Field(default="local_only", min_length=1)
    container_runtime: str = Field(default="podman", min_length=1)


class RuntimeSetupActionResponse(BaseModel):
    id: str
    title: str
    description: str
    command: str | None
    status: str
    reason: str
    category: str


class RuntimeSetupGuideResponse(BaseModel):
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str
    container_runtime: str
    overall_status: str
    actions: list[RuntimeSetupActionResponse]
    notes: list[str]


def to_runtime_setup_action_response(
    action: RuntimeSetupAction,
) -> RuntimeSetupActionResponse:
    return RuntimeSetupActionResponse(
        id=action.id,
        title=action.title,
        description=action.description,
        command=action.command,
        status=action.status,
        reason=action.reason,
        category=action.category,
    )


def to_runtime_setup_guide_response(
    guide: RuntimeSetupGuide,
) -> RuntimeSetupGuideResponse:
    return RuntimeSetupGuideResponse(
        assistant_profile_id=guide.assistant_profile_id,
        laptop_profile_id=guide.laptop_profile_id,
        privacy_mode=guide.privacy_mode,
        container_runtime=guide.container_runtime,
        overall_status=guide.overall_status,
        actions=[
            to_runtime_setup_action_response(action) for action in guide.actions
        ],
        notes=guide.notes,
    )
