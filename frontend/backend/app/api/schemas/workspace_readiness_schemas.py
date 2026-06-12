from pydantic import BaseModel

from app.core.domain.workspace_readiness import (
    WorkspaceCapability,
    WorkspaceReadiness,
)


class WorkspaceCapabilityResponse(BaseModel):
    id: str
    available: bool
    reason: str


class WorkspaceReadinessResponse(BaseModel):
    workspace_id: str
    status: str
    can_scan: bool
    can_analyze: bool
    can_index: bool
    can_ask: bool
    can_execute_commands: bool
    capabilities: list[WorkspaceCapabilityResponse]
    recommended_next_steps: list[str]
    configuration: dict[str, str]


def to_workspace_capability_response(
    capability: WorkspaceCapability,
) -> WorkspaceCapabilityResponse:
    return WorkspaceCapabilityResponse(
        id=capability.id,
        available=capability.available,
        reason=capability.reason,
    )


def to_workspace_readiness_response(
    readiness: WorkspaceReadiness,
) -> WorkspaceReadinessResponse:
    return WorkspaceReadinessResponse(
        workspace_id=readiness.workspace_id,
        status=readiness.status,
        can_scan=readiness.can_scan,
        can_analyze=readiness.can_analyze,
        can_index=readiness.can_index,
        can_ask=readiness.can_ask,
        can_execute_commands=readiness.can_execute_commands,
        capabilities=[
            to_workspace_capability_response(capability)
            for capability in readiness.capabilities
        ],
        recommended_next_steps=readiness.recommended_next_steps,
        configuration=readiness.configuration,
    )
