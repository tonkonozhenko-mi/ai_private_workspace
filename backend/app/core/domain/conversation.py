from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.core.domain.rag import SkillProfileAudit


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_conversation_title(title: str | None) -> str:
    return (title or "New conversation").strip()[:120] or "New conversation"


@dataclass(frozen=True)
class ConversationMessage:
    id: str
    conversation_id: str
    workspace_id: str
    role: str
    content: str
    created_at: str
    sources_count: int = 0
    used_context_chunks: int = 0
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    skill_profile: SkillProfileAudit | None = None


@dataclass(frozen=True)
class WorkspaceConversation:
    id: str
    workspace_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessage] = field(default_factory=list)
    pinned_at: str | None = None
    archived_at: str | None = None


def create_workspace_conversation(workspace_id: str, title: str | None = None) -> WorkspaceConversation:
    now = utc_now_iso()
    return WorkspaceConversation(
        id=str(uuid4()),
        workspace_id=workspace_id,
        title=normalize_conversation_title(title),
        created_at=now,
        updated_at=now,
        messages=[],
        pinned_at=None,
        archived_at=None,
    )


def create_conversation_message(
    *,
    conversation_id: str,
    workspace_id: str,
    role: str,
    content: str,
    sources_count: int = 0,
    used_context_chunks: int = 0,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    latency_ms: int | None = None,
    skill_profile: SkillProfileAudit | None = None,
) -> ConversationMessage:
    return ConversationMessage(
        id=str(uuid4()),
        conversation_id=conversation_id,
        workspace_id=workspace_id,
        role=role,
        content=content,
        created_at=utc_now_iso(),
        sources_count=sources_count,
        used_context_chunks=used_context_chunks,
        llm_provider=llm_provider,
        llm_model=llm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        skill_profile=skill_profile,
    )
