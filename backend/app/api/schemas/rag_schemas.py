from pydantic import BaseModel, Field

from app.core.domain.rag import RagSource, WorkspaceQuestionAnswer


class AskWorkspaceQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class RagSourceResponse(BaseModel):
    chunk_id: str
    source_path: str
    score: float
    preview: str


class WorkspaceQuestionAnswerResponse(BaseModel):
    workspace_id: str
    question: str
    answer: str
    sources: list[RagSourceResponse]
    used_context_chunks: int
    llm_provider: str
    llm_model: str | None
    diagnostic_code: str | None
    diagnostic_message: str | None


def to_rag_source_response(source: RagSource) -> RagSourceResponse:
    return RagSourceResponse(
        chunk_id=source.chunk_id,
        source_path=source.source_path,
        score=source.score,
        preview=source.preview,
    )


def to_workspace_question_answer_response(
    result: WorkspaceQuestionAnswer,
) -> WorkspaceQuestionAnswerResponse:
    return WorkspaceQuestionAnswerResponse(
        workspace_id=result.workspace_id,
        question=result.question,
        answer=result.answer,
        sources=[to_rag_source_response(source) for source in result.sources],
        used_context_chunks=result.used_context_chunks,
        llm_provider=result.llm_provider,
        llm_model=result.llm_model,
        diagnostic_code=result.diagnostic_code,
        diagnostic_message=result.diagnostic_message,
    )
