from typing import Protocol

from app.core.domain.conversation import ConversationMessage, WorkspaceConversation


class ConversationRepositoryPort(Protocol):
    def add_conversation(self, conversation: WorkspaceConversation) -> WorkspaceConversation:
        """Persist a workspace conversation."""

    def get_conversation(self, workspace_id: str, conversation_id: str) -> WorkspaceConversation | None:
        """Return a conversation with its messages."""

    def list_conversations(self, workspace_id: str, limit: int = 30) -> list[WorkspaceConversation]:
        """Return newest workspace conversations first."""

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        """Persist one conversation message."""

    def update_conversation_title(
        self,
        workspace_id: str,
        conversation_id: str,
        title: str,
    ) -> WorkspaceConversation | None:
        """Rename a conversation and return it with messages."""

    def delete_conversation(self, workspace_id: str, conversation_id: str) -> bool:
        """Delete a conversation and messages."""
