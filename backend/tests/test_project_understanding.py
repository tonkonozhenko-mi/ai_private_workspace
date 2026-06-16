from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_understanding_returns_summary_and_caches(tmp_path) -> None:
    _write_text(
        tmp_path / "README.md",
        "understandingtoken: this project is a local-first RAG workspace.",
    )
    workspace = _create_workspace(tmp_path)
    assert _select_llm(workspace["id"], "fake", "fake-llm").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = _generate(workspace["id"])

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["model"] == "fake/fake-llm"
    assert isinstance(result["summary"], str) and result["summary"]
    assert isinstance(result["risks"], list)
    for risk in result["risks"]:
        assert "text" in risk
        assert "file" in risk
    assert "README.md" in result["sources"]
    assert result["is_stale"] is False
    assert result["index_signature"]

    cached = client.get(f"/workspaces/{workspace['id']}/understanding")
    assert cached.status_code == 200
    cached_result = cached.json()
    assert cached_result["model"] == "fake/fake-llm"
    assert cached_result["summary"] == result["summary"]
    assert cached_result["is_stale"] is False


def test_get_understanding_before_generation_returns_404(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/understanding")

    assert response.status_code == 404


def test_generate_understanding_requires_index(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select_llm(workspace["id"], "fake", "fake-llm").status_code == 200

    response = _generate(workspace["id"])

    assert response.status_code == 400
    assert "indexed" in response.json()["detail"].lower()


def test_generate_understanding_requires_selected_llm(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "noselected token project.")
    workspace = _create_workspace(tmp_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200

    response = _generate(workspace["id"])

    assert response.status_code == 400
    assert response.json()["detail"] == "No selected LLM is configured for this workspace."


def test_understanding_is_stale_when_selected_llm_changes(tmp_path) -> None:
    _write_text(tmp_path / "README.md", "staletoken explains the project.")
    workspace = _create_workspace(tmp_path)
    assert _select_llm(workspace["id"], "fake", "fake-llm").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    assert _generate(workspace["id"]).status_code == 200

    # Re-select a different model so the cached understanding becomes stale.
    assert _select_llm(workspace["id"], "fake", "fake-llm-alt").status_code == 200

    cached = client.get(f"/workspaces/{workspace['id']}/understanding")
    assert cached.status_code == 200
    assert cached.json()["model"] == "fake/fake-llm"
    assert cached.json()["is_stale"] is True


def test_unknown_workspace_returns_404() -> None:
    response = _generate("missing-workspace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _generate(workspace_id: str):
    return client.post(f"/workspaces/{workspace_id}/understanding")


def _select_llm(workspace_id: str, provider: str, model: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": "llm",
            "selected_reason": "Understanding test.",
        },
    )


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Understanding Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
