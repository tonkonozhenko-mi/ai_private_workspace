from pydantic import BaseModel, Field

from app.core.domain.rag import RagQualityWarning, RagSource, WorkspaceQuestionAnswer


class SkillContextItemRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=80)
    custom_instructions: str = Field(..., min_length=1, max_length=1200)


class AttachedDocumentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    # Up to ~400 KB of raw text per file; the backend selects relevant excerpts.
    content: str = Field(..., min_length=1, max_length=400_000)


class AskWorkspaceQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    llm_provider: str | None = None
    llm_model: str | None = None
    skill_context: list[SkillContextItemRequest] = Field(default_factory=list, max_length=5)
    images: list[str] = Field(default_factory=list, max_length=4)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    think: bool | None = None
    attached_documents: list[AttachedDocumentRequest] = Field(default_factory=list, max_length=6)


class AskWorkspaceQuestionWithSelectedLLMRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    skill_context: list[SkillContextItemRequest] = Field(default_factory=list, max_length=5)
    images: list[str] = Field(default_factory=list, max_length=4)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    think: bool | None = None
    attached_documents: list[AttachedDocumentRequest] = Field(default_factory=list, max_length=6)


class RagSourceResponse(BaseModel):
    chunk_id: str
    source_path: str
    score: float
    preview: str


class RagQualityWarningResponse(BaseModel):
    code: str
    message: str
    severity: str
    evidence: list[str]


class LLMUsageMetricsResponse(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    tokens_per_second: float | None = None
    provider: str | None = None
    model: str | None = None
    estimated: bool = False


class SkillProfileAuditResponse(BaseModel):
    source: str
    profile: str
    active_skills: list[str]
    guidance_count: int
    updated_at: str | None = None


class WorkspaceQuestionAnswerResponse(BaseModel):
    workspace_id: str
    conversation_id: str | None = None
    conversation_message_id: str | None = None
    question: str
    answer: str
    sources: list[RagSourceResponse]
    used_context_chunks: int
    llm_provider: str
    llm_model: str | None
    diagnostic_code: str | None
    diagnostic_message: str | None
    quality_warnings: list[RagQualityWarningResponse]
    usage: LLMUsageMetricsResponse | None = None
    skill_profile: SkillProfileAuditResponse | None = None


def to_rag_source_response(source: RagSource) -> RagSourceResponse:
    return RagSourceResponse(
        chunk_id=source.chunk_id,
        source_path=source.source_path,
        score=source.score,
        preview=source.preview,
    )


def to_rag_quality_warning_response(
    warning: RagQualityWarning,
) -> RagQualityWarningResponse:
    return RagQualityWarningResponse(
        code=warning.code,
        message=warning.message,
        severity=warning.severity,
        evidence=warning.evidence,
    )


def to_llm_usage_metrics_response(usage) -> LLMUsageMetricsResponse | None:
    if usage is None:
        return None
    return LLMUsageMetricsResponse(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        latency_ms=usage.latency_ms,
        tokens_per_second=usage.tokens_per_second,
        provider=usage.provider,
        model=usage.model,
        estimated=usage.estimated,
    )


def to_skill_profile_audit_response(audit) -> SkillProfileAuditResponse | None:
    if audit is None:
        return None
    return SkillProfileAuditResponse(
        source=audit.source,
        profile=audit.profile,
        active_skills=audit.active_skills,
        guidance_count=audit.guidance_count,
        updated_at=audit.updated_at,
    )


def to_workspace_question_answer_response(
    result: WorkspaceQuestionAnswer,
) -> WorkspaceQuestionAnswerResponse:
    return WorkspaceQuestionAnswerResponse(
        workspace_id=result.workspace_id,
        conversation_id=result.conversation_id,
        conversation_message_id=result.conversation_message_id,
        question=result.question,
        answer=result.answer,
        sources=[to_rag_source_response(source) for source in result.sources],
        used_context_chunks=result.used_context_chunks,
        llm_provider=result.llm_provider,
        llm_model=result.llm_model,
        diagnostic_code=result.diagnostic_code,
        diagnostic_message=result.diagnostic_message,
        quality_warnings=[
            to_rag_quality_warning_response(warning) for warning in result.quality_warnings
        ],
        usage=to_llm_usage_metrics_response(result.usage),
        skill_profile=to_skill_profile_audit_response(result.skill_profile),
    )
