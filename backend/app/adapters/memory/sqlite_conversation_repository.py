import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.conversation import (
    ConversationAnswerNote,
    ConversationMessage,
    WorkspaceConversation,
    normalize_conversation_title,
    update_conversation_answer_note,
    utc_now_iso,
)
from app.core.domain.rag import RagSource, SkillProfileAudit


class SQLiteConversationRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def add_conversation(self, conversation: WorkspaceConversation) -> WorkspaceConversation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_conversations (
                    id, workspace_id, title, created_at, updated_at, pinned_at, archived_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.id,
                    conversation.workspace_id,
                    conversation.title,
                    conversation.created_at,
                    conversation.updated_at,
                    conversation.pinned_at,
                    conversation.archived_at,
                ),
            )
            connection.commit()
        return conversation

    def get_conversation(
        self, workspace_id: str, conversation_id: str
    ) -> WorkspaceConversation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, workspace_id, title, created_at, updated_at, pinned_at, archived_at
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
            pinned_at=row["pinned_at"],
            archived_at=row["archived_at"],
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
        clauses = ["workspace_id = ?"]
        parameters: list[object] = [workspace_id]
        if not include_archived:
            clauses.append("archived_at IS NULL")
        if pinned_only:
            clauses.append("pinned_at IS NOT NULL")
        normalized_search = (search or "").strip().lower()
        if normalized_search:
            clauses.append(
                """
                (LOWER(title) LIKE ? OR id IN (
                    SELECT conversation_id
                    FROM workspace_conversation_messages
                    WHERE workspace_id = ? AND LOWER(content) LIKE ?
                ))
                """
            )
            like_value = f"%{normalized_search}%"
            parameters.extend([like_value, workspace_id, like_value])
        parameters.append(max(0, limit))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, workspace_id, title, created_at, updated_at, pinned_at, archived_at
                FROM workspace_conversations
                WHERE {" AND ".join(clauses)}
                ORDER BY CASE WHEN pinned_at IS NULL THEN 0 ELSE 1 END DESC, updated_at DESC, rowid DESC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        return [self.get_conversation(workspace_id, row["id"]) for row in rows]  # type: ignore[return-value]

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_conversation_messages (
                    id, conversation_id, workspace_id, role, content, created_at,
                    sources_count, used_context_chunks, llm_provider, llm_model,
                    prompt_tokens, completion_tokens, total_tokens, latency_ms,
                    skill_profile_json, sources_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(
                        [self._source_to_dict(source) for source in message.sources], sort_keys=True
                    ),
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
                    (
                        message.content.strip()[:80] or "New conversation",
                        message.created_at,
                        message.conversation_id,
                        message.workspace_id,
                    ),
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

    def update_conversation_title(
        self,
        workspace_id: str,
        conversation_id: str,
        title: str,
    ) -> WorkspaceConversation | None:
        normalized_title = normalize_conversation_title(title)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM workspace_conversations WHERE id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE workspace_conversations
                SET title = ?
                WHERE id = ? AND workspace_id = ?
                """,
                (normalized_title, conversation_id, workspace_id),
            )
            connection.commit()
        return self.get_conversation(workspace_id, conversation_id)

    def set_conversation_pinned(
        self,
        workspace_id: str,
        conversation_id: str,
        pinned: bool,
    ) -> WorkspaceConversation | None:
        pinned_at = utc_now_iso() if pinned else None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM workspace_conversations WHERE id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE workspace_conversations
                SET pinned_at = ?, updated_at = ?
                WHERE id = ? AND workspace_id = ?
                """,
                (pinned_at, utc_now_iso(), conversation_id, workspace_id),
            )
            connection.commit()
        return self.get_conversation(workspace_id, conversation_id)

    def set_conversation_archived(
        self,
        workspace_id: str,
        conversation_id: str,
        archived: bool,
    ) -> WorkspaceConversation | None:
        archived_at = utc_now_iso() if archived else None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM workspace_conversations WHERE id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE workspace_conversations
                SET archived_at = ?, updated_at = ?
                WHERE id = ? AND workspace_id = ?
                """,
                (archived_at, utc_now_iso(), conversation_id, workspace_id),
            )
            connection.commit()
        return self.get_conversation(workspace_id, conversation_id)

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
                "DELETE FROM workspace_answer_notes WHERE conversation_id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            )
            connection.execute(
                "DELETE FROM workspace_conversations WHERE id = ? AND workspace_id = ?",
                (conversation_id, workspace_id),
            )
            connection.commit()
        return True

    def add_answer_note(self, note: ConversationAnswerNote) -> ConversationAnswerNote:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_answer_notes (
                    id, workspace_id, conversation_id, message_id, title, content,
                    source_question, source_paths_json, created_at, updated_at, pinned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.id,
                    note.workspace_id,
                    note.conversation_id,
                    note.message_id,
                    note.title,
                    note.content,
                    note.source_question,
                    json.dumps(note.source_paths, sort_keys=True),
                    note.created_at,
                    note.updated_at,
                    note.pinned_at,
                ),
            )
            connection.commit()
        return note

    def list_answer_notes(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        search: str | None = None,
        pinned_only: bool = False,
        source_path: str | None = None,
    ) -> list[ConversationAnswerNote]:
        clauses = ["workspace_id = ?"]
        parameters: list[object] = [workspace_id]
        normalized_search = (search or "").strip().lower()
        normalized_source_path = (source_path or "").strip().lower()
        if pinned_only:
            clauses.append("pinned_at IS NOT NULL")
        if normalized_source_path:
            clauses.append("LOWER(source_paths_json) LIKE ?")
            parameters.append(f"%{normalized_source_path}%")
        if normalized_search:
            clauses.append(
                "(LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(COALESCE(source_question, '')) LIKE ? OR LOWER(source_paths_json) LIKE ?)"
            )
            like_value = f"%{normalized_search}%"
            parameters.extend([like_value, like_value, like_value, like_value])
        parameters.append(max(0, limit))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, workspace_id, conversation_id, message_id, title, content,
                       source_question, source_paths_json, created_at, updated_at, pinned_at
                FROM workspace_answer_notes
                WHERE {" AND ".join(clauses)}
                ORDER BY CASE WHEN pinned_at IS NULL THEN 0 ELSE 1 END DESC, updated_at DESC, rowid DESC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        return [self._answer_note_from_row(row) for row in rows]

    def update_answer_note(
        self,
        workspace_id: str,
        note_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        pinned: bool | None = None,
    ) -> ConversationAnswerNote | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, workspace_id, conversation_id, message_id, title, content,
                       source_question, source_paths_json, created_at, updated_at, pinned_at
                FROM workspace_answer_notes
                WHERE id = ? AND workspace_id = ?
                """,
                (note_id, workspace_id),
            ).fetchone()
            if row is None:
                return None
            updated = update_conversation_answer_note(
                self._answer_note_from_row(row),
                title=title,
                content=content,
                pinned=pinned,
            )
            if not updated.content:
                return None
            connection.execute(
                """
                UPDATE workspace_answer_notes
                SET title = ?, content = ?, updated_at = ?, pinned_at = ?
                WHERE id = ? AND workspace_id = ?
                """,
                (
                    updated.title,
                    updated.content,
                    updated.updated_at,
                    updated.pinned_at,
                    note_id,
                    workspace_id,
                ),
            )
            connection.commit()
        return updated

    def delete_answer_note(self, workspace_id: str, note_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM workspace_answer_notes WHERE id = ? AND workspace_id = ?",
                (note_id, workspace_id),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "DELETE FROM workspace_answer_notes WHERE id = ? AND workspace_id = ?",
                (note_id, workspace_id),
            )
            connection.commit()
        return True

    def _answer_note_from_row(self, row: sqlite3.Row) -> ConversationAnswerNote:
        return ConversationAnswerNote(
            id=row["id"],
            workspace_id=row["workspace_id"],
            conversation_id=row["conversation_id"],
            message_id=row["message_id"],
            title=row["title"],
            content=row["content"],
            source_question=row["source_question"],
            source_paths=self._source_paths_from_json(row["source_paths_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            pinned_at=row["pinned_at"] if "pinned_at" in row.keys() else None,
        )

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
            sources=self._sources_from_json(row["sources_json"]),
        )

    def _source_to_dict(self, source: RagSource) -> dict[str, object]:
        return {
            "chunk_id": source.chunk_id,
            "source_path": source.source_path,
            "score": source.score,
            "preview": source.preview,
        }

    def _sources_from_json(self, value: str | None) -> list[RagSource]:
        if not value:
            return []
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return []
        sources = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            sources.append(
                RagSource(
                    chunk_id=str(item.get("chunk_id", "")),
                    source_path=str(item.get("source_path", "")),
                    score=float(item.get("score", 0.0)),
                    preview=str(item.get("preview", "")),
                )
            )
        return sources

    def _source_paths_from_json(self, value: str | None) -> list[str]:
        if not value:
            return []
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

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
