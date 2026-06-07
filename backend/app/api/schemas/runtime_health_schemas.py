from pydantic import BaseModel

from app.core.domain.runtime_health import RuntimeComponentHealth, RuntimeHealth


class RuntimeComponentHealthResponse(BaseModel):
    name: str
    configured: bool
    healthy: bool
    status: str
    details: str | None


class RuntimeHealthResponse(BaseModel):
    status: str
    components: list[RuntimeComponentHealthResponse]
    configuration: dict[str, str]


def to_runtime_component_health_response(
    component: RuntimeComponentHealth,
) -> RuntimeComponentHealthResponse:
    return RuntimeComponentHealthResponse(
        name=component.name,
        configured=component.configured,
        healthy=component.healthy,
        status=component.status,
        details=component.details,
    )


def to_runtime_health_response(health: RuntimeHealth) -> RuntimeHealthResponse:
    return RuntimeHealthResponse(
        status=health.status,
        components=[
            to_runtime_component_health_response(component)
            for component in health.components
        ],
        configuration=health.configuration,
    )
