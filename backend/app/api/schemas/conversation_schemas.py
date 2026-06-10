from pydantic import BaseModel, Field

from app.core.domain.conversation import ConversationMessage, WorkspaceConversation
from app.core.domain.rag import SkillProfileAudit


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ConversationMessageResponse(BaseModel):
    id: str
    conversation_id: str
    workspace_id: str
    role: str
    content: str
    created_at: str
    sources_count: int
    used_context_chunks: int
    llm_provider: str | None = None
    llm_model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    skill_profile_source: str | None = None
    skill_profile: str | None = None
    active_skills: list[str] = Field(default_factory=list)
    guidance_count: int = 0


class WorkspaceConversationResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    messages_count: int = 0


def to_conversation_message_response(message: ConversationMessage) -> ConversationMessageResponse:
    profile = message.skill_profile
    return ConversationMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        workspace_id=message.workspace_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        sources_count=message.sources_count,
        used_context_chunks=message.used_context_chunks,
        llm_provider=message.llm_provider,
        llm_model=message.llm_model,
        prompt_tokens=message.prompt_tokens,
        completion_tokens=message.completion_tokens,
        total_tokens=message.total_tokens,
        latency_ms=message.latency_ms,
        skill_profile_source=profile.source if profile else None,
        skill_profile=profile.profile if profile else None,
        active_skills=profile.active_skills if profile else [],
        guidance_count=profile.guidance_count if profile else 0,
    )


def to_workspace_conversation_response(
    conversation: WorkspaceConversation,
    include_messages: bool = True,
) -> WorkspaceConversationResponse:
    messages = (
        [to_conversation_message_response(message) for message in conversation.messages]
        if include_messages
        else []
    )
    return WorkspaceConversationResponse(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=messages,
        messages_count=len(conversation.messages),
    )
