from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_missing_selected_models_returns_blocked_steps(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    timeline_before = client.get(f"/workspaces/{workspace['id']}/timeline").json()

    response = client.get(
        f"/workspaces/{workspace['id']}/local-ai/activation-guide"
    )

    assert response.status_code == 200
    guide = response.json()
    steps = _steps_by_id(guide)
    assert guide["overall_status"] == "blocked"
    assert guide["selected_llm"] is None
    assert guide["selected_embedding"] is None
    assert guide["selected_vector_store"] is None
    assert steps["select_llm"]["status"] == "blocked"
    assert steps["select_embedding"]["status"] == "blocked"
    assert steps["restart_backend"]["status"] == "blocked"
    assert steps["reindex_workspace"]["status"] == "blocked"
    assert steps["ask_with_selected_llm"]["status"] == "blocked"
    assert client.get(f"/workspaces/{workspace['id']}/timeline").json() == timeline_before


def test_selected_ollama_models_produce_pull_qdrant_and_restart_steps(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(
        workspace["id"],
        "ollama",
        "qwen2.5-coder",
        "llm",
    ).status_code == 200
    assert _select(
        workspace["id"],
        "ollama",
        "nomic-embed-text",
        "embedding",
    ).status_code == 200

    guide = client.get(
        f"/workspaces/{workspace['id']}/local-ai/activation-guide"
    ).json()
    steps = _steps_by_id(guide)

    assert guide["overall_status"] == "needs_setup"
    assert guide["selected_llm"] == "ollama/qwen2.5-coder"
    assert guide["selected_embedding"] == "ollama/nomic-embed-text"
    assert guide["selected_vector_store"] == "qdrant"
    assert guide["active_vector_store"] == "memory"
    assert steps["start_ollama"]["command"] == "ollama serve"
    assert steps["pull_ollama_llm_model"]["command"] == (
        "ollama pull qwen2.5-coder"
    )
    assert steps["pull_ollama_embedding_model"]["command"] == (
        "ollama pull nomic-embed-text"
    )
    assert steps["start_qdrant"]["status"] == "needed"
    assert "podman run -d --name qdrant" in steps["start_qdrant"]["command"]
    restart = steps["restart_backend"]["command"]
    assert "VECTOR_STORE=qdrant" in restart
    assert "EMBEDDING_PROVIDER=ollama" in restart
    assert "LLM_PROVIDER=ollama" in restart
    assert "OLLAMA_EMBEDDING_MODEL=nomic-embed-text" in restart
    assert "OLLAMA_LLM_MODEL=qwen2.5-coder" in restart
    assert "QDRANT_URL=http://localhost:6333" in restart
    assert "OLLAMA_BASE_URL=http://localhost:11434" in restart


def test_fake_llm_with_ollama_embedding_keeps_fake_llm_provider(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "ollama",
        "nomic-embed-text",
        "embedding",
    ).status_code == 200

    guide = client.get(
        f"/workspaces/{workspace['id']}/local-ai/activation-guide"
    ).json()
    steps = _steps_by_id(guide)
    restart = steps["restart_backend"]["command"]

    assert "LLM_PROVIDER=fake" in restart
    assert "EMBEDDING_PROVIDER=ollama" in restart
    assert "OLLAMA_EMBEDDING_MODEL=nomic-embed-text" in restart
    assert "OLLAMA_LLM_MODEL=" not in restart
    assert "pull_ollama_llm_model" not in steps
    assert steps["pull_ollama_embedding_model"]["status"] == "optional"


def test_embedding_mismatch_requires_reindex_after_restart(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "ollama",
        "nomic-embed-text",
        "embedding",
    ).status_code == 200

    guide = client.get(
        f"/workspaces/{workspace['id']}/local-ai/activation-guide"
    ).json()
    steps = _steps_by_id(guide)

    assert steps["restart_backend"]["status"] == "needed"
    assert steps["reindex_workspace"]["status"] == "needed"
    assert steps["reindex_workspace"]["command"] == (
        f"curl -X POST http://127.0.0.1:8000/workspaces/{workspace['id']}/index"
    )
    assert steps["ask_with_selected_llm"]["status"] == "optional"
    assert "/ask-selected" in steps["ask_with_selected_llm"]["command"]


def test_matching_fake_models_still_require_index_before_ready(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(workspace["id"], "fake", "fake-llm", "llm").status_code == 200
    assert _select(
        workspace["id"],
        "fake",
        "fake-embedding",
        "embedding",
    ).status_code == 200

    guide = client.get(
        f"/workspaces/{workspace['id']}/local-ai/activation-guide"
    ).json()
    steps = _steps_by_id(guide)

    assert guide["overall_status"] == "needs_setup"
    assert guide["selected_vector_store"] == "memory"
    assert steps["restart_backend"]["status"] == "done"
    assert steps["reindex_workspace"]["status"] == "needed"
    assert "start_qdrant" not in steps


def test_unknown_workspace_returns_404() -> None:
    response = client.get(
        "/workspaces/missing-workspace/local-ai/activation-guide"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _steps_by_id(guide: dict) -> dict[str, dict]:
    return {step["id"]: step for step in guide["steps"]}


def _select(workspace_id: str, provider: str, model: str, model_type: str):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": "Local AI activation guide test.",
        },
    )


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Local AI Activation Guide Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
