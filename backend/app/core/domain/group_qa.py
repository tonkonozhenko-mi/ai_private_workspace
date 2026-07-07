"""Result types for asking a question across a group of repositories.

Every source carries the repository it came from, so a group answer can be
audited the same way a single-repo answer is — you always know which repo a fact
was retrieved from. Group answers now carry the same grounding ``quality_warnings``
and token ``usage`` a single-repo answer does, so the group Ask has parity with the
per-project Ask.
"""

from dataclasses import dataclass, field

from app.core.domain.llm_usage import LLMUsageMetrics
from app.core.domain.rag import RagQualityWarning


@dataclass(frozen=True)
class GroupAnswerSource:
    workspace_id: str
    workspace_name: str
    chunk_id: str
    source_path: str
    score: float
    preview: str


@dataclass(frozen=True)
class GroupRepoContribution:
    workspace_id: str
    workspace_name: str
    indexed: bool
    chunks_used: int


@dataclass(frozen=True)
class GroupQuestionAnswer:
    group_id: str
    question: str
    answer: str
    sources: list[GroupAnswerSource] = field(default_factory=list)
    contributions: list[GroupRepoContribution] = field(default_factory=list)
    used_context_chunks: int = 0
    llm_provider: str = ""
    llm_model: str | None = None
    memory_used: int = 0
    facts_used: int = 0
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None
    # Deterministic grounding checks over the generated answer (missing citations,
    # terms not in context, quote mismatches, …) — same set the single-repo Ask
    # surfaces, so a group answer can be trusted or questioned the same way.
    quality_warnings: list[RagQualityWarning] = field(default_factory=list)
    # Per-request token accounting (prompt/completion tokens, latency, context
    # window). None when the answer was a short-circuit that never called the model.
    usage: LLMUsageMetrics | None = None
