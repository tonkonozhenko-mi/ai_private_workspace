from typing import Protocol

from app.core.domain.conversation import (
    ConversationAnswerNote,
    ConversationMessage,
    WorkspaceConversation,
)


class ConversationRepositoryPort(Protocol):
    def add_conversation(self, conversation: WorkspaceConversation) -> WorkspaceConversation:
        """Persist a workspace conversation."""

    def get_conversation(
        self, workspace_id: str, conversation_id: str
    ) -> WorkspaceConversation | None:
        """Return a conversation with its messages."""

    def list_conversations(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        include_archived: bool = False,
        search: str | None = None,
        pinned_only: bool = False,
    ) -> list[WorkspaceConversation]:
        """Return newest workspace conversations first, with optional filters."""

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        """Persist one conversation message."""

    def update_conversation_title(
        self,
        workspace_id: str,
        conversation_id: str,
        title: str,
    ) -> WorkspaceConversation | None:
        """Rename a conversation and return it with messages."""

    def set_conversation_pinned(
        self,
        workspace_id: str,
        conversation_id: str,
        pinned: bool,
    ) -> WorkspaceConversation | None:
        """Pin or unpin a conversation."""

    def set_conversation_archived(
        self,
        workspace_id: str,
        conversation_id: str,
        archived: bool,
    ) -> WorkspaceConversation | None:
        """Archive or restore a conversation without deleting messages."""

    def delete_conversation(self, workspace_id: str, conversation_id: str) -> bool:
        """Delete a conversation and messages."""

    def add_answer_note(self, note: ConversationAnswerNote) -> ConversationAnswerNote:
        """Persist a reusable answer note."""

    def list_answer_notes(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        search: str | None = None,
    ) -> list[ConversationAnswerNote]:
        """Return reusable answer notes for a workspace."""

    def delete_answer_note(self, workspace_id: str, note_id: str) -> bool:
        """Delete a reusable answer note."""
