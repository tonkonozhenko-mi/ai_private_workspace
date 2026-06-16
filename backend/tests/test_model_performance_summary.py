from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.in_memory_model_experiment_rating_repository import (
    InMemoryModelExperimentRatingRepository,
)
from app.adapters.memory.in_memory_model_experiment_repository import (
    InMemoryModelExperimentRepository,
)
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating
from app.core.domain.model_experiment_run import (
    ModelExperimentCandidateResult,
    ModelExperimentRun,
)
from app.core.domain.workspace import Workspace
from app.core.use_cases.get_model_performance_summary import (
    GetModelPerformanceSummaryInput,
    GetModelPerformanceSummaryUseCase,
)
from app.main import app

client = TestClient(app)


def test_summary_aggregates_candidates_ratings_tags_and_scores() -> None:
    use_case = _performance_use_case()

    summary = use_case.execute(GetModelPerformanceSummaryInput(workspace_id="workspace-1"))

    assert summary.workspace_id == "workspace-1"
    assert [item.model for item in summary.items] == ["alpha", "beta"]

    alpha, beta = summary.items
    assert alpha.experiments_count == 2
    assert alpha.completed_runs_count == 2
    assert alpha.failed_runs_count == 0
    assert alpha.ratings_count == 2
    assert alpha.average_rating == 4.0
    assert alpha.preferred_votes == 1
    assert alpha.average_latency_ms == 1500.0
    assert alpha.average_quality_warnings_count == 0.5
    assert alpha.average_sources_count == 1.5
    assert alpha.common_tags == ["useful", "fast", "grounded", "too_verbose"]
    assert alpha.score == 40

    assert beta.experiments_count == 2
    assert beta.completed_runs_count == 1
    assert beta.failed_runs_count == 1
    assert beta.average_rating == 4.0
    assert beta.preferred_votes == 1
    assert beta.average_latency_ms == 4000.0
    assert beta.average_quality_warnings_count == 1.0
    assert beta.average_sources_count == 0.5
    assert beta.score == 15
    assert "-10: 1 failed or skipped runs." in beta.score_reasons
    assert alpha.score > beta.score


def test_performance_route_reads_saved_runs_and_ratings(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_experiment(workspace["id"])
    rating_response = client.post(
        f"/models/experiments/{run['id']}/ratings",
        json={
            "provider": "fake",
            "model": "fake-llm",
            "rating": 5,
            "is_preferred": True,
            "tags": ["useful", "grounded"],
        },
    )
    assert rating_response.status_code == 201

    response = client.get(f"/workspaces/{workspace['id']}/model-performance")

    assert response.status_code == 200
    summary = response.json()
    assert summary["workspace_id"] == workspace["id"]
    rated = next(item for item in summary["items"] if item["model"] == "fake-llm")
    assert rated["experiments_count"] == 1
    assert rated["completed_runs_count"] == 1
    assert rated["ratings_count"] == 1
    assert rated["average_rating"] == 5.0
    assert rated["preferred_votes"] == 1
    assert rated["common_tags"] == ["grounded", "useful"]


def test_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/model-performance")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _performance_use_case() -> GetModelPerformanceSummaryUseCase:
    workspace_repository = InMemoryWorkspaceRepository()
    experiment_repository = InMemoryModelExperimentRepository()
    rating_repository = InMemoryModelExperimentRatingRepository()
    workspace_repository.create(
        Workspace(
            id="workspace-1",
            name="Performance Workspace",
            project_path="/tmp/performance",
            assistant_mode="developer",
            privacy_mode="local_only",
            created_at=datetime(2026, 6, 8, tzinfo=UTC),
        )
    )
    experiment_repository.save(
        _run(
            "run-1",
            "2026-06-08T10:00:00+00:00",
            [
                _candidate("alpha", status="completed", latency_ms=1000, warnings=0, sources=2),
                _candidate("beta", status="failed", latency_ms=None, warnings=2, sources=0),
            ],
        )
    )
    experiment_repository.save(
        _run(
            "run-2",
            "2026-06-08T11:00:00+00:00",
            [
                _candidate("alpha", status="completed", latency_ms=2000, warnings=1, sources=1),
                _candidate("beta", status="completed", latency_ms=4000, warnings=0, sources=1),
            ],
        )
    )
    rating_repository.save(
        _rating(
            "rating-1",
            "run-1",
            "alpha",
            rating=5,
            preferred=True,
            tags=["useful", "grounded", "fast"],
        )
    )
    rating_repository.save(
        _rating(
            "rating-2",
            "run-2",
            "alpha",
            rating=3,
            tags=["useful", "too_verbose"],
        )
    )
    rating_repository.save(
        _rating(
            "rating-3",
            "run-2",
            "beta",
            rating=4,
            preferred=True,
            tags=["grounded"],
        )
    )
    return GetModelPerformanceSummaryUseCase(
        workspace_repository=workspace_repository,
        model_experiment_repository=experiment_repository,
        rating_repository=rating_repository,
    )


def _run(
    run_id: str,
    created_at: str,
    candidates: list[ModelExperimentCandidateResult],
) -> ModelExperimentRun:
    return ModelExperimentRun(
        id=run_id,
        workspace_id="workspace-1",
        question="Compare performance.",
        experiment_type="llm_comparison",
        status="partial",
        created_at=created_at,
        completed_at=created_at,
        shared_context_sources_count=2,
        candidates=candidates,
        notes=[],
    )


def _candidate(
    model: str,
    *,
    status: str,
    latency_ms: int | None,
    warnings: int,
    sources: int,
) -> ModelExperimentCandidateResult:
    return ModelExperimentCandidateResult(
        provider="fake",
        model=model,
        status=status,
        answer="Answer." if status == "completed" else None,
        error=None if status == "completed" else "Provider error",
        llm_provider="fake",
        llm_model=model,
        used_context_chunks=sources,
        sources_count=sources,
        quality_warnings_count=warnings,
        latency_ms=latency_ms,
    )


def _rating(
    rating_id: str,
    experiment_id: str,
    model: str,
    *,
    rating: int,
    preferred: bool = False,
    tags: list[str],
) -> ModelExperimentCandidateRating:
    return ModelExperimentCandidateRating(
        id=rating_id,
        experiment_id=experiment_id,
        provider="fake",
        model=model,
        rating=rating,
        is_preferred=preferred,
        tags=tags,
        comment=None,
        created_at="2026-06-08T12:00:00+00:00",
    )


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Performance\n\nperformancecontexttoken provides shared context.",
        encoding="utf-8",
    )
    response = client.post(
        "/workspaces",
        json={
            "name": "Performance Route Workspace",
            "project_path": str(project_path),
            "assistant_mode": "developer",
            "privacy_mode": "local_only",
        },
    )
    assert response.status_code == 201
    workspace = response.json()
    assert client.post(f"/workspaces/{workspace['id']}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace['id']}/index").status_code == 200
    return workspace


def _run_experiment(workspace_id: str) -> dict:
    response = client.post(
        "/models/experiments/run",
        json={
            "workspace_id": workspace_id,
            "question": "Explain performancecontexttoken",
            "candidates": [
                {"provider": "fake", "model": "fake-llm"},
                {"provider": "fake", "model": "fake-llm-alt"},
            ],
        },
    )
    assert response.status_code == 200
    return response.json()
