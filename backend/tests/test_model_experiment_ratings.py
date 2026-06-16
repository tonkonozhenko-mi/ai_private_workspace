from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.memory.sqlite_model_experiment_rating_repository import (
    SQLiteModelExperimentRatingRepository,
)
from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating
from app.main import app

client = TestClient(app)


def test_rate_and_list_existing_experiment_candidate(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_experiment(workspace["id"])

    response = _rate_candidate(
        run["id"],
        rating=4,
        is_preferred=True,
        tags=["useful", "fast"],
        comment="  Clear enough for this test.  ",
    )

    assert response.status_code == 201
    rating = response.json()
    assert rating["experiment_id"] == run["id"]
    assert rating["provider"] == "fake"
    assert rating["model"] == "fake-llm"
    assert rating["rating"] == 4
    assert rating["is_preferred"] is True
    assert rating["tags"] == ["useful", "fast"]
    assert rating["comment"] == "Clear enough for this test."

    list_response = client.get(f"/models/experiments/{run['id']}/ratings")

    assert list_response.status_code == 200
    assert list_response.json()[-1] == rating


def test_rating_outside_range_is_rejected(tmp_path) -> None:
    run = _run_experiment(_create_indexed_workspace(tmp_path)["id"])

    response = _rate_candidate(run["id"], rating=6)

    assert response.status_code == 400
    assert response.json()["detail"] == "Rating must be between 1 and 5"


def test_unknown_experiment_and_candidate_are_rejected(tmp_path) -> None:
    unknown_experiment = _rate_candidate("missing-experiment", rating=4)
    run = _run_experiment(_create_indexed_workspace(tmp_path)["id"])
    unknown_candidate = client.post(
        f"/models/experiments/{run['id']}/ratings",
        json={
            "provider": "fake",
            "model": "missing-model",
            "rating": 4,
        },
    )

    assert unknown_experiment.status_code == 404
    assert unknown_experiment.json()["detail"] == "Model experiment not found"
    assert unknown_candidate.status_code == 404
    assert unknown_candidate.json()["detail"] == ("Model experiment candidate not found")
    assert client.get("/models/experiments/missing-experiment/ratings").status_code == 404


def test_rating_creates_workspace_timeline_event(tmp_path) -> None:
    workspace = _create_indexed_workspace(tmp_path)
    run = _run_experiment(workspace["id"])

    rating = _rate_candidate(run["id"], rating=5, is_preferred=True).json()
    events = client.get(f"/workspaces/{workspace['id']}/timeline").json()
    event = events[0]

    assert event["event_type"] == "model_experiment_rated"
    assert event["title"] == "Model experiment rated"
    assert event["summary"] == "Rated fake/fake-llm with 5/5."
    assert event["metadata"] == {
        "experiment_id": run["id"],
        "provider": rating["provider"],
        "model": rating["model"],
        "rating": "5",
        "is_preferred": "true",
    }


def test_comparison_includes_candidate_rating_summary(tmp_path) -> None:
    run = _run_experiment(_create_indexed_workspace(tmp_path)["id"])
    assert _rate_candidate(run["id"], rating=4, is_preferred=True).status_code == 201
    assert _rate_candidate(run["id"], rating=5).status_code == 201

    response = client.get(f"/models/experiments/{run['id']}/comparison")

    assert response.status_code == 200
    comparisons = response.json()["comparisons"]
    rated = next(item for item in comparisons if item["model"] == "fake-llm")
    unrated = next(item for item in comparisons if item["model"] == "fake-llm-alt")
    assert rated["user_ratings_count"] == 2
    assert rated["average_user_rating"] == 4.5
    assert rated["preferred_votes"] == 1
    assert unrated["user_ratings_count"] == 0
    assert unrated["average_user_rating"] is None
    assert unrated["preferred_votes"] == 0


def test_rating_survives_sqlite_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "ratings.db"
    repository = SQLiteModelExperimentRatingRepository(db_path)
    rating = ModelExperimentCandidateRating(
        id="rating-1",
        experiment_id="experiment-1",
        provider="fake",
        model="fake-llm",
        rating=5,
        is_preferred=True,
        tags=["useful", "grounded"],
        comment="Good answer.",
        created_at="2026-06-08T10:00:00+00:00",
    )

    repository.save(rating)
    restarted_repository = SQLiteModelExperimentRatingRepository(db_path)

    assert restarted_repository.list_by_experiment("experiment-1") == [rating]


def _rate_candidate(
    experiment_id: str,
    *,
    rating: int,
    is_preferred: bool = False,
    tags: list[str] | None = None,
    comment: str | None = None,
):
    return client.post(
        f"/models/experiments/{experiment_id}/ratings",
        json={
            "provider": "fake",
            "model": "fake-llm",
            "rating": rating,
            "is_preferred": is_preferred,
            "tags": tags or [],
            "comment": comment,
        },
    )


def _run_experiment(workspace_id: str) -> dict:
    response = client.post(
        "/models/experiments/run",
        json={
            "workspace_id": workspace_id,
            "question": "Explain ratingcontexttoken",
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
        "# Ratings\n\nratingcontexttoken provides shared context.",
        encoding="utf-8",
    )
    response = client.post(
        "/workspaces",
        json={
            "name": "Rating Workspace",
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
