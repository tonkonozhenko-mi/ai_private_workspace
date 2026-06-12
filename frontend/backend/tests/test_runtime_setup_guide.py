from fastapi.testclient import TestClient

from app.core.domain.runtime_health import RuntimeComponentHealth
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.core.use_cases.get_runtime_setup_guide import (
    GetRuntimeSetupGuideInput,
    GetRuntimeSetupGuideUseCase,
)
from app.main import app


client = TestClient(app)


class StaticHealthChecker:
    def __init__(self, component: RuntimeComponentHealth) -> None:
        self.component = component

    def check(self) -> RuntimeComponentHealth:
        return self.component


def test_default_runtime_recommends_qdrant_ollama_and_backend_restart() -> None:
    response = _setup_guide("podman")

    assert response.status_code == 200
    guide = response.json()
    actions = _actions_by_id(guide)
    assert guide["overall_status"] == "needs_setup"
    assert actions["start_qdrant_podman"]["status"] == "needed"
    assert actions["verify_ollama_runtime"]["status"] == "needed"
    assert actions["pull_ollama_embedding_model"]["status"] == "needed"
    assert actions["pull_ollama_llm_model"]["status"] == "needed"
    assert actions["start_backend"]["status"] == "needed"
    assert actions["start_podman_machine"]["command"] == "podman machine start"


def test_matching_healthy_runtime_marks_actions_done() -> None:
    guide = _direct_guide(
        configuration=_recommended_configuration(),
        components=[
            _component("qdrant", healthy=True),
            _component(
                "ollama",
                healthy=True,
                metadata={
                    "reachable": "true",
                    "installed_models": "nomic-embed-text:latest,llama3.2:latest",
                },
            ),
        ],
    )

    assert guide.overall_status == "ready"
    assert guide.actions
    assert all(action.status == "done" for action in guide.actions)


def test_configured_unhealthy_runtime_produces_degraded_guide() -> None:
    guide = _direct_guide(
        configuration=_recommended_configuration(),
        components=[
            _component("qdrant", healthy=False, status="unreachable"),
            _component(
                "ollama",
                healthy=True,
                metadata={
                    "reachable": "true",
                    "installed_models": "nomic-embed-text,llama3.2",
                },
            ),
        ],
    )

    assert guide.overall_status == "degraded"
    assert _domain_actions_by_id(guide)["start_qdrant_podman"].status == "needed"


def test_reachable_ollama_with_missing_model_only_needs_missing_model_pull() -> None:
    guide = _direct_guide(
        configuration=_recommended_configuration(),
        components=[
            _component("qdrant", healthy=True),
            _component(
                "ollama",
                healthy=False,
                status="error",
                metadata={
                    "reachable": "true",
                    "installed_models": "nomic-embed-text:latest",
                    "missing_models": "llama3.2",
                },
            ),
        ],
    )
    actions = _domain_actions_by_id(guide)

    assert actions["verify_ollama_runtime"].status == "done"
    assert actions["pull_ollama_embedding_model"].status == "done"
    assert actions["pull_ollama_llm_model"].status == "needed"
    assert actions["start_backend"].status == "done"


def test_docker_guide_uses_docker_oriented_qdrant_command() -> None:
    response = _setup_guide("docker")

    assert response.status_code == 200
    actions = _actions_by_id(response.json())
    assert actions["start_qdrant_docker"]["command"] == "docker compose up -d qdrant"
    assert "start_qdrant_podman" not in actions
    assert "start_podman_machine" not in actions


def test_invalid_container_runtime_returns_clear_error() -> None:
    response = _setup_guide("containerd")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown container runtime: containerd"


def _setup_guide(container_runtime: str):
    return client.post(
        "/runtime/setup-guide",
        json={
            "assistant_profile_id": "devops",
            "laptop_profile_id": "balanced",
            "privacy_mode": "local_only",
            "container_runtime": container_runtime,
        },
    )


def _direct_guide(
    configuration: dict[str, str],
    components: list[RuntimeComponentHealth],
):
    health_use_case = GetRuntimeHealthUseCase(
        health_checkers=[StaticHealthChecker(component) for component in components],
        configuration=configuration,
    )
    return GetRuntimeSetupGuideUseCase(
        runtime_health_use_case=health_use_case,
    ).execute(
        GetRuntimeSetupGuideInput(
            assistant_profile_id="devops",
            laptop_profile_id="balanced",
            privacy_mode="local_only",
            container_runtime="podman",
        )
    )


def _recommended_configuration() -> dict[str, str]:
    return {
        "VECTOR_STORE": "qdrant",
        "EMBEDDING_PROVIDER": "ollama",
        "LLM_PROVIDER": "ollama",
    }


def _component(
    name: str,
    healthy: bool,
    status: str = "ok",
    metadata: dict[str, str] | None = None,
) -> RuntimeComponentHealth:
    return RuntimeComponentHealth(
        name=name,
        configured=True,
        healthy=healthy,
        status=status,
        details=None,
        metadata=metadata or {},
    )


def _actions_by_id(guide: dict) -> dict[str, dict]:
    return {action["id"]: action for action in guide["actions"]}


def _domain_actions_by_id(guide) -> dict:
    return {action.id: action for action in guide.actions}
