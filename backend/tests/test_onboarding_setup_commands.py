from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_balanced_devops_podman_includes_qdrant_and_ollama_setup() -> None:
    response = _setup_commands("devops", "balanced", "podman")

    assert response.status_code == 200
    result = response.json()
    commands = {command["id"]: command for command in result["commands"]}
    assert commands["start_podman_machine"]["command"] == "podman machine start"
    assert commands["start_qdrant_podman"]["command"] == (
        "podman run -d --name qdrant -p 6333:6333 "
        "-v qdrant_data:/qdrant/storage docker.io/qdrant/qdrant:latest"
    )
    assert commands["pull_ollama_embedding_model"]["command"] == ("ollama pull nomic-embed-text")
    assert commands["pull_ollama_llm_model"]["command"] == "ollama pull llama3.2"
    assert commands["start_backend"]["command"] == (
        "VECTOR_STORE=qdrant EMBEDDING_PROVIDER=ollama LLM_PROVIDER=ollama "
        "QDRANT_URL=http://localhost:6333 OLLAMA_BASE_URL=http://localhost:11434 "
        "uvicorn app.main:app --reload"
    )


def test_docker_runtime_includes_docker_compose_qdrant_command() -> None:
    response = _setup_commands("devops", "balanced", "docker")

    assert response.status_code == 200
    commands = {command["id"]: command for command in response.json()["commands"]}
    assert commands["start_qdrant_docker"]["command"] == "docker compose up -d qdrant"
    assert "start_podman_machine" not in commands
    assert "start_qdrant_podman" not in commands


def test_low_power_does_not_require_qdrant_or_ollama_setup() -> None:
    response = _setup_commands("developer", "low_power", "podman")

    assert response.status_code == 200
    commands = response.json()["commands"]
    assert [command["id"] for command in commands] == ["start_backend"]
    assert commands[0]["command"] == (
        "VECTOR_STORE=memory EMBEDDING_PROVIDER=fake LLM_PROVIDER=fake "
        "uvicorn app.main:app --reload"
    )


def test_setup_commands_are_classified_and_never_auto_proposed() -> None:
    response = _setup_commands("devops", "balanced", "podman")

    assert response.status_code == 200
    commands = response.json()["commands"]
    assert commands
    assert all(command["can_be_proposed"] is False for command in commands)
    assert all(
        command["risk"] in {"readonly", "write", "destructive", "unknown"} for command in commands
    )


def test_invalid_container_runtime_returns_clear_error() -> None:
    response = _setup_commands("devops", "balanced", "containerd")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown container runtime: containerd"


def test_invalid_profile_is_reported_without_side_effects() -> None:
    response = _setup_commands("missing-profile", "balanced", "podman")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown assistant profile: missing-profile"


def _setup_commands(
    assistant_profile_id: str,
    laptop_profile_id: str,
    container_runtime: str,
):
    return client.post(
        "/onboarding/setup-commands",
        json={
            "assistant_profile_id": assistant_profile_id,
            "laptop_profile_id": laptop_profile_id,
            "privacy_mode": "local_only",
            "container_runtime": container_runtime,
        },
    )
