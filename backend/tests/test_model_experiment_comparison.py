from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.in_memory_model_experiment_repository import (
    InMemoryModelExperimentRepository,
)
from app.core.domain.model_experiment_run import (
    ModelExperimentCandidateResult,
    ModelExperimentRun,
)
from app.core.use_cases.get_model_experiment_comparison import (
    GetModelExperimentComparisonUseCase,
)
from app.main import app


client = TestClient(app)


def test_comparison_for_completed_run_returns_candidates(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_experiment(workspace["id"])

    response = client.get(f"/models/experiments/{run['id']}/comparison")

    assert response.status_code == 200
    summary = response.json()
    assert summary["experiment_id"] == run["id"]
    assert summary["workspace_id"] == workspace["id"]
    assert summary["experiment_status"] == "completed"
    assert summary["candidates_count"] == 2
    assert summary["completed_candidates_count"] == 2
    assert summary["failed_candidates_count"] == 0
    assert len(summary["comparisons"]) == 2
    assert all(comparison["answer_length"] > 0 for comparison in summary["comparisons"])


def test_recommended_candidate_is_selected_by_score_and_ties_use_first() -> None:
    repository = InMemoryModelExperimentRepository()
    run = _run(
        candidates=[
            _candidate(model="first", answer="a" * 101, latency_ms=100),
            _candidate(model="second", answer="b" * 101, latency_ms=100),
        ]
    )
    repository.save(run)

    summary = GetModelExperimentComparisonUseCase(repository).execute(run.id)

    assert summary.comparisons[0].score == 80
    assert summary.comparisons[1].score == 80
    assert summary.recommended_candidate == "fake/first"


def test_failed_candidates_are_penalized_and_excluded_from_winner() -> None:
    repository = InMemoryModelExperimentRepository()
    run = _run(
        status="partial",
        candidates=[
            _candidate(model="winner", answer="Completed answer.", latency_ms=100),
            _candidate(
                model="failed",
                status="failed",
                answer=None,
                error="Provider unavailable",
                sources_count=0,
                latency_ms=None,
            ),
        ],
    )
    repository.save(run)

    summary = GetModelExperimentComparisonUseCase(repository).execute(run.id)
    failed = summary.comparisons[1]

    assert summary.recommended_candidate == "fake/winner"
    assert summary.completed_candidates_count == 1
    assert summary.failed_candidates_count == 1
    assert failed.score < 0
    assert "Candidate failed: Provider unavailable" in failed.warnings
    assert "Candidate has no retrieved sources." in failed.warnings
    assert "Candidate answer is empty." in failed.warnings


def test_quality_warnings_reduce_score_with_capped_penalty() -> None:
    repository = InMemoryModelExperimentRepository()
    run = _run(
        candidates=[
            _candidate(model="clean", quality_warnings_count=0),
            _candidate(model="warned", quality_warnings_count=8),
        ]
    )
    repository.save(run)

    summary = GetModelExperimentComparisonUseCase(repository).execute(run.id)
    clean, warned = summary.comparisons

    assert clean.score - warned.score == 40
    assert "-30: Candidate has 8 quality warnings." in warned.score_reasons
    assert "Candidate has 8 quality warnings." in warned.warnings
    assert summary.recommended_candidate == "fake/clean"


def test_no_completed_candidates_returns_no_recommendation() -> None:
    repository = InMemoryModelExperimentRepository()
    run = _run(
        status="failed",
        candidates=[
            _candidate(model="failed", status="failed", answer=None),
            _candidate(model="skipped", status="skipped", answer=None),
        ],
    )
    repository.save(run)

    summary = GetModelExperimentComparisonUseCase(repository).execute(run.id)

    assert summary.recommended_candidate is None
    assert summary.completed_candidates_count == 0
    assert summary.failed_candidates_count == 2


def test_comparison_does_not_mutate_saved_experiment() -> None:
    repository = InMemoryModelExperimentRepository()
    run = _run()
    repository.save(run)

    GetModelExperimentComparisonUseCase(repository).execute(run.id)

    assert repository.get(run.id) == run


def test_unknown_experiment_comparison_returns_404() -> None:
    response = client.get("/models/experiments/missing-experiment/comparison")

    assert response.status_code == 404
    assert response.json()["detail"] == "Model experiment not found"


def _run(
    *,
    status: str = "completed",
    candidates: list[ModelExperimentCandidateResult] | None = None,
) -> ModelExperimentRun:
    return ModelExperimentRun(
        id="comparison-run",
        workspace_id="workspace-1",
        question="Compare models.",
        experiment_type="llm_comparison",
        status=status,
        created_at="2026-06-08T10:00:00+00:00",
        completed_at="2026-06-08T10:00:01+00:00",
        shared_context_sources_count=1,
        candidates=candidates or [_candidate(model="fake-llm")],
        notes=["Shared context."],
    )


def _candidate(
    *,
    model: str,
    status: str = "completed",
    answer: str | None = "A concise completed answer.",
    error: str | None = None,
    sources_count: int = 1,
    quality_warnings_count: int = 0,
    latency_ms: int | None = 100,
) -> ModelExperimentCandidateResult:
    return ModelExperimentCandidateResult(
        provider="fake",
        model=model,
        status=status,
        answer=answer,
        error=error,
        llm_provider="fake",
        llm_model=model,
        used_context_chunks=sources_count,
        sources_count=sources_count,
        quality_warnings_count=quality_warnings_count,
        latency_ms=latency_ms,
    )


def _run_experiment(workspace_id: str) -> dict:
    response = client.post(
        "/models/experiments/run",
        json={
            "workspace_id": workspace_id,
            "question": "Explain comparisoncontexttoken",
            "candidates": [
                {"provider": "fake", "model": "fake-llm"},
                {"provider": "fake", "model": "fake-llm-alt"},
            ],
        },
    )
    assert response.status_code == 200
    return response.json()


def _create_indexed_workspace(project_path: Path) -> dict:
    (project_path / "README.md").write_text(
        "# Comparison\n\ncomparisoncontexttoken provides shared context.",
        encoding="utf-8",
    )
    response = client.post(
        "/workspaces",
        json={
            "name": "Comparison Workspace",
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
