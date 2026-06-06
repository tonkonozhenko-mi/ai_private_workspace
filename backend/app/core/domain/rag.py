from dataclasses import dataclass, field


@dataclass(frozen=True)
class RagSource:
    chunk_id: str
    source_path: str
    score: float
    preview: str


@dataclass(frozen=True)
class RagQualityWarning:
    code: str
    message: str
    severity: str
    evidence: list[str]


@dataclass(frozen=True)
class WorkspaceQuestionAnswer:
    workspace_id: str
    question: str
    answer: str
    sources: list[RagSource]
    used_context_chunks: int
    llm_provider: str
    llm_model: str | None
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None
    quality_warnings: list[RagQualityWarning] = field(default_factory=list)
