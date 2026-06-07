import httpx
from fastapi.testclient import TestClient

from app.adapters.runtime_health.command_runner_health_checker import (
    CommandRunnerHealthChecker,
)
from app.adapters.runtime_health.ollama_runtime_health_checker import (
    OllamaRuntimeHealthChecker,
)
from app.adapters.runtime_health.qdrant_runtime_health_checker import (
    QdrantRuntimeHealthChecker,
)
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.main import app


client = TestClient(app)


def test_default_runtime_health_is_ok_with_optional_services_not_configured() -> None:
    response = client.get("/runtime/health")

    assert response.status_code == 200
    health = response.json()
    assert health["status"] == "ok"
    assert _component(health, "qdrant")["status"] == "not_configured"
    assert _component(health, "ollama")["status"] == "not_configured"
    command_runner = _component(health, "command_runner")
    assert command_runner["status"] == "ok"
    assert command_runner["healthy"] is True
    assert health["configuration"]["VECTOR_STORE"] == "memory"
    assert health["configuration"]["EMBEDDING_PROVIDER"] == "fake"
    assert health["configuration"]["LLM_PROVIDER"] == "fake"
    assert health["configuration"]["COMMAND_RUNNER"] == "fake"


def test_qdrant_configured_but_unreachable_returns_degraded() -> None:
    checker = QdrantRuntimeHealthChecker(
        vector_store="qdrant",
        qdrant_url="http://qdrant.test",
        client=_client_that_cannot_connect(),
    )

    health = GetRuntimeHealthUseCase(
        health_checkers=[checker],
        configuration={"VECTOR_STORE": "qdrant"},
    ).execute()

    assert health.status == "degraded"
    assert health.components[0].configured is True
    assert health.components[0].healthy is False
    assert health.components[0].status == "unreachable"


def test_ollama_configured_but_unreachable_returns_degraded() -> None:
    checker = OllamaRuntimeHealthChecker(
        embedding_provider="ollama",
        llm_provider="fake",
        base_url="http://ollama.test",
        embedding_model="nomic-embed-text",
        llm_model="llama3.2",
        client=_client_that_cannot_connect(),
    )

    health = GetRuntimeHealthUseCase(
        health_checkers=[checker],
        configuration={"EMBEDDING_PROVIDER": "ollama"},
    ).execute()

    assert health.status == "degraded"
    assert health.components[0].configured is True
    assert health.components[0].healthy is False
    assert health.components[0].status == "unreachable"


def test_ollama_health_verifies_configured_models() -> None:
    checker = OllamaRuntimeHealthChecker(
        embedding_provider="ollama",
        llm_provider="ollama",
        base_url="http://ollama.test",
        embedding_model="nomic-embed-text",
        llm_model="llama3.2",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "models": [
                            {"name": "nomic-embed-text:latest"},
                            {"model": "llama3.2:latest"},
                        ]
                    },
                )
            )
        ),
    )

    component = checker.check()

    assert component.configured is True
    assert component.healthy is True
    assert component.status == "ok"
    assert "nomic-embed-text" in component.details
    assert "llama3.2" in component.details


def test_command_runner_fake_reports_ok_without_execution() -> None:
    component = CommandRunnerHealthChecker(command_runner="fake").check()

    assert component.configured is True
    assert component.healthy is True
    assert component.status == "ok"
    assert "no real commands are executed" in component.details


def _component(health: dict, name: str) -> dict:
    return next(
        component
        for component in health["components"]
        if component["name"] == name
    )


def _client_that_cannot_connect() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))
