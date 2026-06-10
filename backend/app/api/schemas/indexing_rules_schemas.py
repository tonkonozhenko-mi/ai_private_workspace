from pydantic import BaseModel, Field

from app.core.domain.indexing_rules import IndexingRulesProfile


class WorkspaceIndexingRulesRequest(BaseModel):
    profile: str = Field(default="balanced")
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)


class WorkspaceIndexingRulesResponse(BaseModel):
    workspace_id: str
    profile: str
    include_patterns: list[str]
    exclude_patterns: list[str]
    include_rules_count: int
    exclude_rules_count: int
    updated_at: str | None = None
    source: str = "saved"


def to_workspace_indexing_rules_response(
    profile: IndexingRulesProfile,
    *,
    source: str = "saved",
) -> WorkspaceIndexingRulesResponse:
    return WorkspaceIndexingRulesResponse(
        workspace_id=profile.workspace_id,
        profile=profile.profile,
        include_patterns=list(profile.include_patterns),
        exclude_patterns=list(profile.exclude_patterns),
        include_rules_count=profile.include_rules_count,
        exclude_rules_count=profile.exclude_rules_count,
        updated_at=profile.updated_at,
        source=source,
    )
