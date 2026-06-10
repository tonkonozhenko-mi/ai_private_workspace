import json
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.conversation import ConversationMessage, WorkspaceConversation
from app.core.domain.rag import SkillProfileAudit


class SQLiteConversationRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def add_conversation(self, conversation: WorkspaceConversation) -> WorkspaceConversation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_conversations (
                    id, workspace_id, title, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation.id,
                    conversation.workspace_id,
                    conversation.title,
                    conversation.created_at,
                    conversation.updated_at,
                ),
            )
            connection.commit()
        return conversation

    def get_conversation(self, workspace_id: str, conversation_id: str) -> WorkspaceConversation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, workspace_id, title, created_at, updated_at
                FROM workspace_conversations
                WHERE id = ? AND workspace_id = ?
                """,
                (conversation_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            message_rows = connection.execute(
                """
                SELECT * FROM workspace_conversation_messages
                WHERE conversation_id = ? AND workspace_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (conversation_id, workspace_id),
            ).fetchall()

        return WorkspaceConversation(
            id=row["id"],
            workspace_id=row["workspace_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            messages=[self._message_from_row(message_row) for message_row in message_rows],
        )

    def list_conversations(self, workspace_id: str, limit: int = 30) -> list[WorkspaceConversation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, workspace_id, title, created_at, updated_at
                FROM workspace_conversations
                WHERE workspace_id = ?
                ORDER BY updated_at DESC, rowid DESC
                LIMIT ?
                """,
                (workspace_id, max(0, limit)),
            ).fetchall()
        return [
            self.get_conversation(workspace_id, row["id"])
            for row in rows
        ]  # type: ignore[return-value]

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_conversation_messages (
                    id, conversation_id, workspace_id, role, content, created_at,
                    sources_count, used_context_chunks, llm_provider, llm_model,
                    prompt_tokens, completion_tokens, total_tokens, latency_ms,
                    skill_profile_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.conversation_id,
                    message.workspace_id,
                    message.role,
                    message.content,
                    message.created_at,
                    message.sources_count,
                    message.used_context_chunks,
                    message.llm_provider,
                    message.llm_model,
                    message.prompt_tokens,
                    message.completion_tokens,
                    message.total_tokens,
                    message.latency_ms,
                    json.dumps(self._skill_profile_to_dict(message.skill_profile), sort_keys=True),
                ),
            )
            if message.role == "user":
                connection.execute(
                    """
                    UPDATE workspace_conversations
                    SET title = CASE WHEN title = 'New conversation' THEN ? ELSE title END,
                        updated_at = ?
                    WHERE id = ? AND workspace_id = ?
                    """,
                    (message.content.strip()[:80] or "New conversation", message.created_at, message.conversation_id, message.workspace_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE workspace_conversations
                    SET updated_at = ?
                    WHERE id = ? AND workspace_id = ?
                    """,
                    (message.created_at, message.conversation_id, message.workspace_id),
                )
            connection.commit()
        return message

    def delete_conversation(self, workspace_id: str, conversation_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM workspace_conversations WHERE id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "DELETE FROM workspace_conversation_messages WHERE conversation_id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            )
            connection.execute(
                "DELETE FROM workspace_conversations WHERE id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            )
            connection.commit()
        return True

    def _message_from_row(self, row: sqlite3.Row) -> ConversationMessage:
        return ConversationMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            workspace_id=row["workspace_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
            sources_count=row["sources_count"],
            used_context_chunks=row["used_context_chunks"],
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            latency_ms=row["latency_ms"],
            skill_profile=self._skill_profile_from_json(row["skill_profile_json"]),
        )

    def _skill_profile_to_dict(self, profile: SkillProfileAudit | None) -> dict[str, object] | None:
        if profile is None:
            return None
        return {
            "source": profile.source,
            "profile": profile.profile,
            "active_skills": profile.active_skills,
            "guidance_count": profile.guidance_count,
            "updated_at": profile.updated_at,
        }

    def _skill_profile_from_json(self, value: str | None) -> SkillProfileAudit | None:
        if not value:
            return None
        data = json.loads(value)
        if data is None:
            return None
        return SkillProfileAudit(
            source=data.get("source", "default"),
            profile=data.get("profile", "workspace"),
            active_skills=list(data.get("active_skills", [])),
            guidance_count=int(data.get("guidance_count", 0)),
            updated_at=data.get("updated_at"),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
