from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import readiness_configuration
from app.main import app


client = TestClient(app)


def test_missing_selected_llm_returns_400(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _ask_selected(workspace["id"], "What is this project?")

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "No selected LLM is configured for this workspace."
    )


def test_selected_fake_llm_reuses_existing_ask_behavior(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "selectedasktoken explains the project.")
    workspace = _create_workspace(tmp_path)
    assert _select_llm(workspace["id"], "fake", "fake-llm").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = _ask_selected(workspace["id"], "Explain selectedasktoken", limit=3)

    assert response.status_code == 200
    result = response.json()
    assert "Fake answer" in result["answer"]
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm"
    assert result["used_context_chunks"] >= 1
    assert result["sources"][0]["source_path"] == "README.md"
    assert result["diagnostic_code"] is None


def test_selected_fake_llm_alt_reports_selected_model(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select_llm(
        workspace["id"],
        "fake",
        "fake-llm-alt",
    ).status_code == 200

    response = _ask_selected(workspace["id"], "What is this project?")

    assert response.status_code == 200
    result = response.json()
    assert result["diagnostic_code"] == "workspace_not_indexed"
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm-alt"


def test_selected_unsupported_provider_returns_400(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select_llm(
        workspace["id"],
        "custom",
        "private-model",
    ).status_code == 200

    response = _ask_selected(workspace["id"], "What is this project?")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported selected LLM provider: custom"


def test_selected_embedding_mismatch_adds_quality_warning(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select_llm(workspace["id"], "fake", "fake-llm").status_code == 200
    assert _select_model(
        workspace["id"],
        "ollama",
        "nomic-embed-text",
        "embedding",
    ).status_code == 200

    response = _ask_selected(workspace["id"], "What is this project?")

    assert response.status_code == 200
    warning = next(
        warning
        for warning in response.json()["quality_warnings"]
        if warning["code"] == "selected_embedding_not_active"
    )
    assert (
        warning["message"]
        == "Answer used active embedding/index configuration, not the selected "
        "embedding model."
    )
    assert warning["severity"] == "low"
    assert "selected=ollama/nomic-embed-text" in warning["evidence"]
    assert "active=fake/fake-embedding" in warning["evidence"]


def test_selected_ask_records_actual_model_and_selected_flag_in_timeline(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select_llm(
        workspace["id"],
        "fake",
        "fake-llm-alt",
    ).status_code == 200

    response = _ask_selected(workspace["id"], "What is this project?")

    assert response.status_code == 200
    question_event = next(
        event
        for event in client.get(f"/workspaces/{workspace['id']}/timeline").json()
        if event["event_type"] == "workspace_question_asked"
    )
    assert question_event["metadata"]["llm_provider"] == "fake"
    assert question_event["metadata"]["llm_model"] == "fake-llm-alt"
    assert question_event["metadata"]["asked_with_selected_llm"] == "true"


def test_selected_ask_does_not_change_runtime_configuration(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select_llm(
        workspace["id"],
        "fake",
        "fake-llm-alt",
    ).status_code == 200
    configuration_before = dict(readiness_configuration)

    response = _ask_selected(workspace["id"], "What is this project?")

    assert response.status_code == 200
    assert readiness_configuration == configuration_before
    status = client.get(
        f"/workspaces/{workspace['id']}/models/selection/status"
    ).json()
    assert status["llm_status"]["active_provider"] == "fake"
    assert status["llm_status"]["active_model"] == "fake-llm"
    assert status["llm_status"]["status"] == "runtime_mismatch"


def test_unknown_workspace_returns_404() -> None:
    response = _ask_selected("missing-workspace", "What is this project?")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _ask_selected(workspace_id: str, question: str, limit: int = 5):
    return client.post(
        f"/workspaces/{workspace_id}/ask-selected",
        json={"question": question, "limit": limit},
    )


def _select_llm(workspace_id: str, provider: str, model: str):
    return _select_model(workspace_id, provider, model, "llm")


def _select_model(
    workspace_id: str,
    provider: str,
    model: str,
    model_type: str,
):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Selected ask test.",
        },
    )


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Selected Ask Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
