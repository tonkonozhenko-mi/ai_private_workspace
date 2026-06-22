"""Answer ratings + nudges HTTP API.

The user's 👍/👎 are logged locally; from the recent history we derive at most two
honest nudges (try a bigger model / rebuild the search context). Nothing here
retrains a model — it's a deterministic read over a local log.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import answer_rating_repository
from app.core.use_cases.manage_answer_ratings import (
    AnswerRatingValidationError,
    GetRatingNudgesUseCase,
    RecordAnswerRatingInput,
    RecordAnswerRatingUseCase,
)

router = APIRouter(tags=["answer-ratings"])


class RatingRequest(BaseModel):
    verdict: str  # "up" | "down"
    llm_model: str = ""
    context_chunks: int = 0


class NudgeResponse(BaseModel):
    kind: str
    title: str
    detail: str
    action: str


class NudgesResponse(BaseModel):
    nudges: list[NudgeResponse]


@router.post("/workspaces/{workspace_id}/answer-ratings", status_code=status.HTTP_201_CREATED)
def record_answer_rating(workspace_id: str, request: RatingRequest) -> dict:
    try:
        RecordAnswerRatingUseCase(answer_rating_repository).execute(
            RecordAnswerRatingInput(
                workspace_id=workspace_id,
                verdict=request.verdict,
                llm_model=request.llm_model,
                context_chunks=request.context_chunks,
            )
        )
    except AnswerRatingValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"recorded": True}


@router.get("/workspaces/{workspace_id}/answer-ratings/nudges", response_model=NudgesResponse)
def get_answer_rating_nudges(workspace_id: str) -> NudgesResponse:
    nudges = GetRatingNudgesUseCase(answer_rating_repository).execute(workspace_id)
    return NudgesResponse(nudges=[NudgeResponse(**vars(n)) for n in nudges])
