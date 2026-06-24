"""Answer ratings: pure nudge logic + record/get use cases (in-memory)."""

from app.adapters.memory.in_memory_answer_rating_repository import (
    InMemoryAnswerRatingRepository,
)
from app.core.domain.answer_rating import AnswerRating, compute_rating_nudges
from app.core.use_cases.manage_answer_ratings import (
    AnswerRatingValidationError,
    GetRatingNudgesUseCase,
    RecordAnswerRatingInput,
    RecordAnswerRatingUseCase,
)


def _r(i, verdict, model="ollama/small", chunks=5):
    return AnswerRating(
        id=str(i),
        workspace_id="w",
        verdict=verdict,
        llm_model=model,
        context_chunks=chunks,
        created_at=f"2026-06-{i:02d}",
    )


def test_no_nudges_below_minimum():
    ratings = [_r(1, "down"), _r(2, "down")]  # only 2
    assert compute_rating_nudges(ratings) == []


def test_no_nudges_when_mostly_positive():
    ratings = [_r(i, "up") for i in range(1, 9)] + [_r(9, "down")]
    assert compute_rating_nudges(ratings) == []


def test_model_nudge_on_high_down_rate():
    ratings = [_r(i, "down", model="ollama/tiny") for i in range(1, 6)] + [
        _r(6, "up"),
    ]
    nudges = compute_rating_nudges(ratings)
    kinds = {n.kind for n in nudges}
    assert "model" in kinds
    model_nudge = next(n for n in nudges if n.kind == "model")
    assert "ollama/tiny" in model_nudge.detail
    assert model_nudge.action == "open_models"


def test_retrieval_nudge_when_downs_had_no_context():
    ratings = [_r(i, "down", chunks=0) for i in range(1, 6)] + [_r(6, "up")]
    nudges = compute_rating_nudges(ratings)
    retrieval = [n for n in nudges if n.kind == "retrieval"]
    assert retrieval and retrieval[0].action == "rebuild_context"


def test_retrieval_nudge_absent_when_downs_had_context():
    # 5 downs but all with rich context → no retrieval nudge (model nudge may fire)
    ratings = [_r(i, "down", chunks=6) for i in range(1, 6)] + [_r(6, "up")]
    nudges = compute_rating_nudges(ratings)
    assert all(n.kind != "retrieval" for n in nudges)


def test_record_validates_verdict():
    uc = RecordAnswerRatingUseCase(InMemoryAnswerRatingRepository())
    try:
        uc.execute(RecordAnswerRatingInput(workspace_id="w", verdict="meh"))
        raise AssertionError("expected validation error")
    except AnswerRatingValidationError:
        pass


def test_record_and_get_nudges_end_to_end():
    repo = InMemoryAnswerRatingRepository()
    rec = RecordAnswerRatingUseCase(repo)
    for _ in range(5):
        rec.execute(
            RecordAnswerRatingInput(
                workspace_id="w", verdict="down", llm_model="m", context_chunks=0
            )
        )
    rec.execute(
        RecordAnswerRatingInput(workspace_id="w", verdict="up", llm_model="m", context_chunks=3)
    )
    nudges = GetRatingNudgesUseCase(repo).execute("w")
    assert {n.kind for n in nudges} >= {"model", "retrieval"}
    # other workspace is unaffected
    assert GetRatingNudgesUseCase(repo).execute("other") == []
