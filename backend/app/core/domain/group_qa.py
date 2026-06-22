"""Result types for asking a question across a group of repositories.

Every source carries the repository it came from, so a group answer can be
audited the same way a single-repo answer is — you always know which repo a fact
was retrieved from.
"""

from dataclasses import dataclass, field


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
