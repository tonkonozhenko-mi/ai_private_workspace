from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_workspace_model_selection_repository import (
    SQLiteWorkspaceModelSelectionRepository,
)
from app.api.dependencies import workspace_model_selection_repository
from app.core.domain.workspace_model_selection import (
    EMBEDDING_CHANGE_NOTE,
    PREFERENCE_ONLY_NOTE,
    UNKNOWN_CATALOG_NOTE,
    WorkspaceModelSelection,
    WorkspaceSelectedModel,
)
from app.main import app


client = TestClient(app)


def test_new_workspace_returns_empty_selection(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/models/selection")

    assert response.status_code == 200
    selection = response.json()
    assert selection["workspace_id"] == workspace["id"]
    assert selection["selected_llm"] is None
    assert selection["selected_embedding"] is None
    assert "No workspace model selections have been saved." in selection["notes"]


def test_select_llm_and_embedding_preserve_each_other(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    llm_response = _select(
        workspace["id"],
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
        selected_reason="  Recommended for DevOps questions.  ",
    )
    embedding_response = _select(
        workspace["id"],
        provider="ollama",
        model="nomic-embed-text",
        model_type="embedding",
    )

    assert llm_response.status_code == 200
    assert llm_response.json()["selected_llm"]["selected_reason"] == (
        "Recommended for DevOps questions."
    )
    assert llm_response.json()["selected_embedding"] is None

    assert embedding_response.status_code == 200
    selection = embedding_response.json()
    assert selection["selected_llm"]["model"] == "qwen2.5-coder"
    assert selection["selected_embedding"]["model"] == "nomic-embed-text"
    assert "Selected LLM does not match active runtime configuration." in selection[
        "notes"
    ]
    assert (
        "Selected embedding model does not match active runtime configuration."
        in selection["notes"]
    )


def test_changing_embedding_selection_adds_reindex_note_and_preserves_llm(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path)
    assert _select(
        workspace["id"],
        provider="fake",
        model="fake-llm",
        model_type="llm",
    ).status_code == 200
    assert _select(
        workspace["id"],
        provider="fake",
        model="fake-embedding",
        model_type="embedding",
    ).status_code == 200

    response = _select(
        workspace["id"],
        provider="ollama",
        model="nomic-embed-text",
        model_type="embedding",
    )

    assert response.status_code == 200
    selection = response.json()
    assert selection["selected_llm"]["model"] == "fake-llm"
    assert selection["selected_embedding"]["model"] == "nomic-embed-text"
    assert EMBEDDING_CHANGE_NOTE in selection["notes"]
    assert "Selected LLM matches active runtime configuration." in selection["notes"]

    later_llm_update = _select(
        workspace["id"],
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
    ).json()
    assert EMBEDDING_CHANGE_NOTE in later_llm_update["notes"]


def test_unknown_model_is_allowed_with_note(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _select(
        workspace["id"],
        provider="custom",
        model="private-model",
        model_type="llm",
    )

    assert response.status_code == 200
    assert response.json()["selected_llm"]["model"] == "private-model"
    assert UNKNOWN_CATALOG_NOTE in response.json()["notes"]


def test_known_model_drops_stale_unknown_catalog_note(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)
    workspace_model_selection_repository.save(
        WorkspaceModelSelection(
            workspace_id=workspace["id"],
            selected_llm=WorkspaceSelectedModel(
                provider="ollama",
                model="qwen2.5-coder",
                model_type="llm",
                selected_at="2026-06-13T00:00:00+00:00",
                selected_reason="Previously discovered model.",
            ),
            selected_embedding=None,
            notes=[PREFERENCE_ONLY_NOTE, UNKNOWN_CATALOG_NOTE],
        )
    )

    response = client.get(f"/workspaces/{workspace['id']}/models/selection")

    assert response.status_code == 200
    assert UNKNOWN_CATALOG_NOTE not in response.json()["notes"]


def test_invalid_model_type_and_unknown_workspace_are_rejected(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    invalid_type = _select(
        workspace["id"],
        provider="ollama",
        model="qwen2.5-coder",
        model_type="reranker",
    )
    missing_get = client.get("/workspaces/missing-workspace/models/selection")
    missing_put = _select(
        "missing-workspace",
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
    )

    assert invalid_type.status_code == 400
    assert invalid_type.json()["detail"] == "Unknown model type: reranker"
    assert missing_get.status_code == 404
    assert missing_put.status_code == 404


def test_selection_creates_timeline_event(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _select(
        workspace["id"],
        provider="ollama",
        model="qwen2.5-coder",
        model_type="llm",
    )
    event = client.get(f"/workspaces/{workspace['id']}/timeline").json()[0]

    assert response.status_code == 200
    assert event["event_type"] == "workspace_model_selected"
    assert event["title"] == "Workspace model selected"
    assert event["summary"] == "Selected ollama/qwen2.5-coder for llm."
    assert event["metadata"] == {
        "provider": "ollama",
        "model": "qwen2.5-coder",
        "model_type": "llm",
    }
    assert client.get(f"/workspaces/{workspace['id']}/index/status").json()[
        "status"
    ] == "not_indexed"


def test_selection_survives_sqlite_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "selections.db"
    repository = SQLiteWorkspaceModelSelectionRepository(db_path)
    selection = WorkspaceModelSelection(
        workspace_id="workspace-1",
        selected_llm=WorkspaceSelectedModel(
            provider="ollama",
            model="qwen2.5-coder",
            model_type="llm",
            selected_at="2026-06-08T10:00:00+00:00",
            selected_reason="Preferred coding model.",
        ),
        selected_embedding=None,
        notes=["Preference metadata only."],
    )

    repository.save(selection)
    restarted_repository = SQLiteWorkspaceModelSelectionRepository(db_path)

    assert restarted_repository.get(selection.workspace_id) == selection


def _select(
    workspace_id: str,
    *,
    provider: str,
    model: str,
    model_type: str,
    selected_reason: str | None = None,
):
    return client.put(
        f"/workspaces/{workspace_id}/models/selection",
        json={
            "provider": provider,
            "model": model,
            "model_type": model_type,
            "selected_reason": selected_reason,
        },
    )


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Selection Workspace",
            "project_path": str(project_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    return response.json()
