from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_model_experiment_repository import (
    SQLiteModelExperimentRepository,
)
from app.api.routes import models as model_routes
from app.core.domain.model_experiment_run import (
    ModelExperimentCandidateResult,
    ModelExperimentRun,
)
from app.main import app


client = TestClient(app)


def test_run_fake_comparison_on_indexed_workspace_creates_completed_run(
    tmp_path,
) -> None:
    workspace = _create_indexed_workspace(tmp_path)

    response = _run_experiment(workspace["id"])

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["shared_context_sources_count"] > 0
    assert len(run["candidates"]) == 2
    assert {candidate["status"] for candidate in run["candidates"]} == {"completed"}
    assert all("Fake answer" in candidate["answer"] for candidate in run["candidates"])
    assert all(candidate["sources_count"] > 0 for candidate in run["candidates"])
    assert all(
        candidate["used_context_chunks"] == run["shared_context_sources_count"]
        for candidate in run["candidates"]
    )
    assert [candidate["llm_model"] for candidate in run["candidates"]] == [
        "fake-llm",
        "fake-llm-alt",
    ]


def test_experiment_retrieves_shared_context_once(tmp_path, monkeypatch) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    counting_store = _CountingVectorStore(model_routes.vector_store)
    monkeypatch.setattr(model_routes, "vector_store", counting_store)

    response = _run_experiment(workspace["id"])

    assert response.status_code == 200
    assert counting_store.search_calls == 1
    assert response.json()["notes"] == [
        "All candidates used the same retrieved context chunks and prompt."
    ]


def test_run_requires_indexed_workspace(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = _run_experiment(workspace["id"])

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Workspace must be indexed before running a model experiment"
    )
    assert client.get(f"/workspaces/{workspace['id']}/model-experiments").json() == []


def test_one_failed_candidate_leads_partial_status(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)

    response = _run_experiment(
        workspace["id"],
        candidates=[
            {"provider": "fake", "model": "fake-llm"},
            {"provider": "custom", "model": "private-model"},
        ],
    )

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "partial"
    assert [candidate["status"] for candidate in run["candidates"]] == [
        "completed",
        "failed",
    ]
    assert run["candidates"][1]["error"] == "Unsupported LLM provider: custom"


def test_saved_run_can_be_fetched_and_listed(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_experiment(workspace["id"]).json()

    get_response = client.get(f"/models/experiments/{run['id']}")
    list_response = client.get(
        f"/workspaces/{workspace['id']}/model-experiments?limit=20"
    )

    assert get_response.status_code == 200
    assert get_response.json() == run
    assert list_response.status_code == 200
    assert list_response.json()[0] == run


def test_model_experiment_creates_timeline_event(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_experiment(workspace["id"]).json()

    events = client.get(f"/workspaces/{workspace['id']}/timeline").json()
    event = events[0]

    assert event["event_type"] == "model_experiment_run"
    assert event["title"] == "Model experiment run"
    assert event["summary"] == "Compared 2 model candidates."
    assert event["metadata"] == {
        "experiment_id": run["id"],
        "candidates_count": "2",
        "status": "completed",
    }


def test_index_metadata_without_active_context_saves_failed_run(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    model_routes.vector_store.clear_workspace(workspace["id"])

    response = _run_experiment(workspace["id"])

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "failed"
    assert run["shared_context_sources_count"] == 0
    assert {candidate["status"] for candidate in run["candidates"]} == {"skipped"}
    assert any("no context chunks" in note for note in run["notes"])
    assert client.get(f"/models/experiments/{run['id']}").status_code == 200


def test_unknown_experiment_and_workspace_return_404() -> None:
    assert client.get("/models/experiments/missing-experiment").status_code == 404
    assert (
        client.get("/workspaces/missing-workspace/model-experiments").status_code
        == 404
    )


def test_experiment_run_survives_sqlite_repository_recreation(tmp_path) -> None:
    repository = SQLiteModelExperimentRepository(tmp_path / "experiments.db")
    run = ModelExperimentRun(
        id="experiment-1",
        workspace_id="workspace-1",
        question="What changed?",
        experiment_type="llm_comparison",
        status="completed",
        created_at="2026-06-08T10:00:00+00:00",
        completed_at="2026-06-08T10:00:01+00:00",
        shared_context_sources_count=1,
        candidates=[
            ModelExperimentCandidateResult(
                provider="fake",
                model="fake-llm",
                status="completed",
                answer="Fake answer.",
                error=None,
                llm_provider="fake",
                llm_model="fake-llm",
                used_context_chunks=1,
                sources_count=1,
                quality_warnings_count=0,
                latency_ms=1,
            )
        ],
        notes=["Shared context."],
    )

    repository.save(run)
    restarted_repository = SQLiteModelExperimentRepository(
        tmp_path / "experiments.db"
    )

    assert restarted_repository.get(run.id) == run
    assert restarted_repository.list_by_workspace(run.workspace_id) == [run]


def _run_experiment(
    workspace_id: str,
    candidates: list[dict] | None = None,
):
    return client.post(
        "/models/experiments/run",
        json={
            "workspace_id": workspace_id,
            "question": "Explain experimentcontexttoken",
            "experiment_type": "llm_comparison",
            "limit": 3,
            "candidates": candidates
            or [
                {"provider": "fake", "model": "fake-llm"},
                {"provider": "fake", "model": "fake-llm-alt"},
            ],
        },
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    _write_text(
        project_path / "README.md",
        "# Experiment\n\nexperimentcontexttoken provides shared context.",
    )
    workspace = _create_workspace(project_path)
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    return workspace


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Experiment Run Workspace",
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


class _CountingVectorStore:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.search_calls = 0

    def search(self, *args, **kwargs):
        self.search_calls += 1
        return self.delegate.search(*args, **kwargs)
