from datetime import datetime

from pydantic import BaseModel, Field

from app.api.schemas.onboarding_schemas import (
    OnboardingPlanResponse,
    to_onboarding_plan_response,
)
from app.api.schemas.onboarding_setup_schemas import (
    OnboardingSetupCommandsResponse,
    to_onboarding_setup_commands_response,
)
from app.api.schemas.runtime_setup_guide_schemas import (
    RuntimeSetupGuideResponse,
    to_runtime_setup_guide_response,
)
from app.api.schemas.workspace_readiness_schemas import (
    WorkspaceReadinessResponse,
    to_workspace_readiness_response,
)
from app.core.domain.onboarding_bootstrap import OnboardingBootstrapResult
from app.core.domain.workspace import Workspace


class BootstrapWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1)
    project_path: str = Field(..., min_length=1)
    assistant_profile_id: str = Field(..., min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    privacy_mode: str = Field(default="local_only", min_length=1)
    container_runtime: str = Field(default="podman", min_length=1)


class BootstrapWorkspaceResponse(BaseModel):
    id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: datetime
    archived_at: str | None
    persistence: str = "saved"


class OnboardingBootstrapResponse(BaseModel):
    workspace: BootstrapWorkspaceResponse
    onboarding_plan: OnboardingPlanResponse
    setup_commands: OnboardingSetupCommandsResponse
    runtime_setup_guide: RuntimeSetupGuideResponse
    readiness: WorkspaceReadinessResponse
    next_steps: list[str]


def to_bootstrap_workspace_response(workspace: Workspace) -> BootstrapWorkspaceResponse:
    return BootstrapWorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        project_path=workspace.project_path,
        assistant_mode=workspace.assistant_mode,
        privacy_mode=workspace.privacy_mode,
        created_at=workspace.created_at,
        archived_at=workspace.archived_at,
        persistence=workspace.persistence,
    )


def to_onboarding_bootstrap_response(
    result: OnboardingBootstrapResult,
) -> OnboardingBootstrapResponse:
    return OnboardingBootstrapResponse(
        workspace=to_bootstrap_workspace_response(result.workspace),
        onboarding_plan=to_onboarding_plan_response(result.onboarding_plan),
        setup_commands=to_onboarding_setup_commands_response(result.setup_commands),
        runtime_setup_guide=to_runtime_setup_guide_response(result.runtime_setup_guide),
        readiness=to_workspace_readiness_response(result.readiness),
        next_steps=result.next_steps,
    )
