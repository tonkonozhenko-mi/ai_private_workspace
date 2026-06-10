from app.core.domain.conversation import ConversationMessage, WorkspaceConversation, normalize_conversation_title, utc_now_iso


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._conversations: dict[str, WorkspaceConversation] = {}
        self._messages: dict[str, list[ConversationMessage]] = {}

    def add_conversation(self, conversation: WorkspaceConversation) -> WorkspaceConversation:
        self._conversations[conversation.id] = conversation
        self._messages.setdefault(conversation.id, [])
        return conversation

    def get_conversation(self, workspace_id: str, conversation_id: str) -> WorkspaceConversation | None:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.workspace_id != workspace_id:
            return None
        return WorkspaceConversation(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=list(self._messages.get(conversation_id, [])),
            pinned_at=conversation.pinned_at,
            archived_at=conversation.archived_at,
        )

    def list_conversations(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        include_archived: bool = False,
        search: str | None = None,
        pinned_only: bool = False,
    ) -> list[WorkspaceConversation]:
        normalized_search = (search or "").strip().lower()
        conversations = [
            self.get_conversation(workspace_id, conversation.id)
            for conversation in self._conversations.values()
            if conversation.workspace_id == workspace_id
        ]
        filtered = []
        for conversation in conversations:
            if conversation is None:
                continue
            if not include_archived and conversation.archived_at is not None:
                continue
            if pinned_only and conversation.pinned_at is None:
                continue
            if normalized_search:
                haystack = " ".join([
                    conversation.title,
                    *(message.content for message in conversation.messages),
                ]).lower()
                if normalized_search not in haystack:
                    continue
            filtered.append(conversation)
        return sorted(
            filtered,
            key=lambda conversation: (conversation.pinned_at is not None, conversation.updated_at),
            reverse=True,
        )[: max(0, limit)]

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        self._messages.setdefault(message.conversation_id, []).append(message)
        conversation = self._conversations.get(message.conversation_id)
        if conversation is not None:
            title = conversation.title
            if title == "New conversation" and message.role == "user":
                title = message.content.strip()[:80] or title
            self._conversations[conversation.id] = WorkspaceConversation(
                id=conversation.id,
                workspace_id=conversation.workspace_id,
                title=title,
                created_at=conversation.created_at,
                updated_at=message.created_at,
                messages=[],
                pinned_at=conversation.pinned_at,
                archived_at=conversation.archived_at,
            )
        return message

    def update_conversation_title(
        self,
        workspace_id: str,
        conversation_id: str,
        title: str,
    ) -> WorkspaceConversation | None:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.workspace_id != workspace_id:
            return None
        updated = WorkspaceConversation(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            title=normalize_conversation_title(title),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=[],
            pinned_at=conversation.pinned_at,
            archived_at=conversation.archived_at,
        )
        self._conversations[conversation_id] = updated
        return self.get_conversation(workspace_id, conversation_id)

    def set_conversation_pinned(
        self,
        workspace_id: str,
        conversation_id: str,
        pinned: bool,
    ) -> WorkspaceConversation | None:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.workspace_id != workspace_id:
            return None
        updated = WorkspaceConversation(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=utc_now_iso(),
            messages=[],
            pinned_at=utc_now_iso() if pinned else None,
            archived_at=conversation.archived_at,
        )
        self._conversations[conversation_id] = updated
        return self.get_conversation(workspace_id, conversation_id)

    def set_conversation_archived(
        self,
        workspace_id: str,
        conversation_id: str,
        archived: bool,
    ) -> WorkspaceConversation | None:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.workspace_id != workspace_id:
            return None
        updated = WorkspaceConversation(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=utc_now_iso(),
            messages=[],
            pinned_at=conversation.pinned_at,
            archived_at=utc_now_iso() if archived else None,
        )
        self._conversations[conversation_id] = updated
        return self.get_conversation(workspace_id, conversation_id)

    def delete_conversation(self, workspace_id: str, conversation_id: str) -> bool:
        conversation = self._conversations.get(conversation_id)
        if conversation is None or conversation.workspace_id != workspace_id:
            return False
        del self._conversations[conversation_id]
        self._messages.pop(conversation_id, None)
        return True
