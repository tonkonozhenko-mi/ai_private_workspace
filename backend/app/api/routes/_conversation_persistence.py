"""Writing a question and its answer into a conversation.

The use cases only ever *read* the thread; the route owns the write, and until
now that write lived inside the workspace routes where only they could reach it.
A group needed the same thing, so it moved here rather than being copied — the
group Ask has spent three releases quietly missing fixes that the single path
received, and every one of those was a copy that stopped being a twin.

The scope id is opaque on purpose: a workspace id from one caller, a group id
from the other. The conversation store never inspected it (no foreign key, no
validation, just string equality), and the project-memory store has been keyed by
group ids the same way since groups existed.
"""

from __future__ import annotations

from app.core.domain.conversation import (
    create_conversation_message,
    create_workspace_conversation,
)


def ensure_conversation(repository, scope_id: str, conversation_id: str | None, title=None):
    """The thread this question belongs to, creating it on the first question.

    Returns ``None`` when the named conversation does not exist, so the caller can
    answer with its own 404 — a thread that vanished is not an error worth
    inventing a new answer for.
    """
    if conversation_id:
        return repository.get_conversation(scope_id, conversation_id)
    return repository.add_conversation(create_workspace_conversation(scope_id, title=title))


def persist_turn(
    repository,
    scope_id: str,
    conversation_id: str,
    question: str,
    answer_text: str,
    *,
    sources_count: int = 0,
    used_context_chunks: int = 0,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    usage=None,
    sources=None,
    skill_profile=None,
):
    """Record the question and the answer as two turns; return the assistant message.

    The pair is what makes the next question answerable: "and where is that
    configured?" is only a question if the turn before it survived.
    """
    repository.add_message(
        create_conversation_message(
            conversation_id=conversation_id,
            workspace_id=scope_id,
            role="user",
            content=question,
        )
    )
    return repository.add_message(
        create_conversation_message(
            conversation_id=conversation_id,
            workspace_id=scope_id,
            role="assistant",
            content=answer_text,
            sources_count=sources_count,
            used_context_chunks=used_context_chunks,
            llm_provider=llm_provider,
            llm_model=llm_model,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            latency_ms=usage.latency_ms if usage else None,
            skill_profile=skill_profile,
            sources=sources,
        )
    )
