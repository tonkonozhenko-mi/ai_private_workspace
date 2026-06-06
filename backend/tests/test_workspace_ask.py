from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ask_unknown_workspace_returns_404() -> None:
    response = client.post(
        "/workspaces/missing-workspace/ask",
        json={"question": "What is this project?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_ask_without_indexed_context_returns_no_context_answer(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _ask(workspace["id"], "What is this project?")

    assert response.status_code == 200
    result = response.json()
    assert result["answer"] == "No indexed context was found for this workspace."
    assert result["sources"] == []
    assert result["used_context_chunks"] == 0
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm"


def test_ask_after_indexing_returns_sources_and_fake_answer(tmp_path) -> None:
    _write_text(
        tmp_path / "README.md",
        "raganswertoken describes the workspace architecture and indexing flow.",
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = _ask(workspace["id"], "Explain raganswertoken")

    assert response.status_code == 200
    result = response.json()
    assert "Fake answer" in result["answer"]
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake-llm"
    assert result["used_context_chunks"] >= 1
    assert result["sources"]
    assert result["sources"][0]["source_path"] == "README.md"
    assert "raganswertoken" in result["sources"][0]["preview"]


def test_ask_source_preview_is_limited_to_200_characters(tmp_path) -> None:
    content = "previewtoken " + ("a" * 400)
    _write_text(tmp_path / "README.md", content)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200
    index_response = client.post(f"/workspaces/{workspace['id']}/index")
    assert index_response.status_code == 200

    response = _ask(workspace["id"], "previewtoken")

    assert response.status_code == 200
    source = response.json()["sources"][0]
    assert source["source_path"] == "README.md"
    assert len(source["preview"]) == 200


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "RAG Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _ask(workspace_id: str, question: str):
    return client.post(
        f"/workspaces/{workspace_id}/ask",
        json={
            "question": question,
            "limit": 5,
        },
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
