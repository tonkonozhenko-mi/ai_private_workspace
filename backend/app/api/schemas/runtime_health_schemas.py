from pydantic import BaseModel

from app.core.domain.runtime_health import RuntimeComponentHealth, RuntimeHealth


class RuntimeComponentHealthResponse(BaseModel):
    name: str
    configured: bool
    healthy: bool
    status: str
    details: str | None
    metadata: dict[str, str]


class RuntimeHealthResponse(BaseModel):
    status: str
    components: list[RuntimeComponentHealthResponse]
    configuration: dict[str, str]


class RuntimeTroubleshootingStepResponse(BaseModel):
    title: str
    detail: str
    copy_command: str | None = None


class RuntimeTroubleshootingIssueResponse(BaseModel):
    id: str
    title: str
    severity: str
    component: str
    summary: str
    details: str
    steps: list[RuntimeTroubleshootingStepResponse]


class RuntimeTroubleshootingResponse(BaseModel):
    status: str
    summary: str
    issues: list[RuntimeTroubleshootingIssueResponse]
    quick_checks: list[RuntimeTroubleshootingStepResponse]
    safe_restart_commands: list[RuntimeTroubleshootingStepResponse]
    safety_note: str


def to_runtime_component_health_response(
    component: RuntimeComponentHealth,
) -> RuntimeComponentHealthResponse:
    return RuntimeComponentHealthResponse(
        name=component.name,
        configured=component.configured,
        healthy=component.healthy,
        status=component.status,
        details=component.details,
        metadata=component.metadata,
    )


def to_runtime_health_response(health: RuntimeHealth) -> RuntimeHealthResponse:
    return RuntimeHealthResponse(
        status=health.status,
        components=[
            to_runtime_component_health_response(component) for component in health.components
        ],
        configuration=health.configuration,
    )
