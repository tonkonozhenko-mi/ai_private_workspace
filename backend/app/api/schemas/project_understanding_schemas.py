from pydantic import BaseModel

from app.core.domain.project_understanding import ProjectUnderstanding


class ProjectRiskResponse(BaseModel):
    text: str
    file: str | None = None


class ProjectUnderstandingResponse(BaseModel):
    workspace_id: str
    model: str
    generated_at: str
    index_signature: str
    summary: str
    risks: list[ProjectRiskResponse]
    sources: list[str]
    is_stale: bool


def to_project_understanding_response(
    understanding: ProjectUnderstanding,
    is_stale: bool,
) -> ProjectUnderstandingResponse:
    return ProjectUnderstandingResponse(
        workspace_id=understanding.workspace_id,
        model=understanding.model,
        generated_at=understanding.generated_at,
        index_signature=understanding.index_signature,
        summary=understanding.summary,
        risks=[
            ProjectRiskResponse(text=risk.text, file=risk.source_file)
            for risk in understanding.risks
        ],
        sources=list(understanding.sources),
        is_stale=is_stale,
    )
