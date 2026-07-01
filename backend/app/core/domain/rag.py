from dataclasses import dataclass, field

from app.core.domain.llm_usage import LLMUsageMetrics


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
class SkillProfileAudit:
    source: str
    profile: str
    active_skills: list[str]
    guidance_count: int
    updated_at: str | None = None


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
    usage: LLMUsageMetrics | None = None
    skill_profile: SkillProfileAudit | None = None
    conversation_id: str | None = None
    conversation_message_id: str | None = None
    project_memory_used: int = 0
    project_facts_used: int = 0
    # For a "Why this answer?" panel: the notes/guardrails that actually went into
    # the prompt (each {kind, text, grounding}); guardrails as plain strings.
    project_memory_details: list = field(default_factory=list)
    project_guardrails_used: list = field(default_factory=list)
