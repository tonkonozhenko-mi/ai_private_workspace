from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.command import CommandProposal


class SQLiteCommandRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def create(self, proposal: CommandProposal) -> CommandProposal:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_commands (
                    id,
                    workspace_id,
                    command,
                    cwd,
                    reason,
                    risk,
                    status,
                    created_at,
                    approved_at,
                    rejected_at,
                    executed_at,
                    stdout,
                    stderr,
                    exit_code
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(proposal),
            )
            connection.commit()
        return proposal

    def get(self, command_id: str) -> CommandProposal | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    workspace_id,
                    command,
                    cwd,
                    reason,
                    risk,
                    status,
                    created_at,
                    approved_at,
                    rejected_at,
                    executed_at,
                    stdout,
                    stderr,
                    exit_code
                FROM workspace_commands
                WHERE id = ?
                """,
                (command_id,),
            ).fetchone()

        if row is None:
            return None
        return self._from_row(row)

    def list_by_workspace(self, workspace_id: str) -> list[CommandProposal]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    workspace_id,
                    command,
                    cwd,
                    reason,
                    risk,
                    status,
                    created_at,
                    approved_at,
                    rejected_at,
                    executed_at,
                    stdout,
                    stderr,
                    exit_code
                FROM workspace_commands
                WHERE workspace_id = ?
                ORDER BY created_at ASC
                """,
                (workspace_id,),
            ).fetchall()

        return [self._from_row(row) for row in rows]

    def update(self, proposal: CommandProposal) -> CommandProposal:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE workspace_commands
                SET
                    workspace_id = ?,
                    command = ?,
                    cwd = ?,
                    reason = ?,
                    risk = ?,
                    status = ?,
                    created_at = ?,
                    approved_at = ?,
                    rejected_at = ?,
                    executed_at = ?,
                    stdout = ?,
                    stderr = ?,
                    exit_code = ?
                WHERE id = ?
                """,
                (
                    proposal.workspace_id,
                    proposal.command,
                    proposal.cwd,
                    proposal.reason,
                    proposal.risk,
                    proposal.status,
                    proposal.created_at,
                    proposal.approved_at,
                    proposal.rejected_at,
                    proposal.executed_at,
                    proposal.stdout,
                    proposal.stderr,
                    proposal.exit_code,
                    proposal.id,
                ),
            )
            connection.commit()
        return proposal

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_row(proposal: CommandProposal) -> tuple:
        return (
            proposal.id,
            proposal.workspace_id,
            proposal.command,
            proposal.cwd,
            proposal.reason,
            proposal.risk,
            proposal.status,
            proposal.created_at,
            proposal.approved_at,
            proposal.rejected_at,
            proposal.executed_at,
            proposal.stdout,
            proposal.stderr,
            proposal.exit_code,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CommandProposal:
        return CommandProposal(
            id=row["id"],
            workspace_id=row["workspace_id"],
            command=row["command"],
            cwd=row["cwd"],
            reason=row["reason"],
            risk=row["risk"],
            status=row["status"],
            created_at=row["created_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
            executed_at=row["executed_at"],
            stdout=row["stdout"],
            stderr=row["stderr"],
            exit_code=row["exit_code"],
        )
