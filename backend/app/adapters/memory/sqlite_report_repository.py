import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.report import SavedWorkspaceReport, update_saved_workspace_report


class SQLiteReportRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def add_report(self, report: SavedWorkspaceReport) -> SavedWorkspaceReport:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_saved_reports (
                    id, workspace_id, report_type, title, summary, export_markdown, export_text,
                    report_json, generated_from_json, created_at, updated_at, pinned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.workspace_id,
                    report.report_type,
                    report.title,
                    report.summary,
                    report.export_markdown,
                    report.export_text,
                    json.dumps(report.report_json, sort_keys=True),
                    json.dumps(report.generated_from, sort_keys=True),
                    report.created_at,
                    report.updated_at,
                    report.pinned_at,
                ),
            )
            connection.commit()
        return report

    def get_report(self, workspace_id: str, report_id: str) -> SavedWorkspaceReport | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM workspace_saved_reports
                WHERE id = ? AND workspace_id = ?
                """,
                (report_id, workspace_id),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def list_reports(
        self,
        workspace_id: str,
        limit: int = 30,
        *,
        search: str | None = None,
        report_type: str | None = None,
        pinned_only: bool = False,
    ) -> list[SavedWorkspaceReport]:
        clauses = ["workspace_id = ?"]
        params: list[object] = [workspace_id]
        normalized_search = (search or "").strip().lower()
        normalized_type = (report_type or "").strip().lower()
        if normalized_type:
            clauses.append("report_type = ?")
            params.append(normalized_type)
        if pinned_only:
            clauses.append("pinned_at IS NOT NULL")
        if normalized_search:
            clauses.append(
                "(LOWER(title) LIKE ? OR LOWER(summary) LIKE ? OR LOWER(export_markdown) LIKE ?)"
            )
            like = f"%{normalized_search}%"
            params.extend([like, like, like])
        params.append(max(0, limit))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM workspace_saved_reports
                WHERE {" AND ".join(clauses)}
                ORDER BY CASE WHEN pinned_at IS NULL THEN 0 ELSE 1 END DESC, updated_at DESC, rowid DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_report(
        self,
        workspace_id: str,
        report_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        export_markdown: str | None = None,
        export_text: str | None = None,
        report_json: dict[str, object] | None = None,
        generated_from: list[str] | None = None,
        pinned: bool | None = None,
    ) -> SavedWorkspaceReport | None:
        current = self.get_report(workspace_id, report_id)
        if current is None:
            return None
        updated = update_saved_workspace_report(
            current,
            title=title,
            summary=summary,
            export_markdown=export_markdown,
            export_text=export_text,
            report_json=report_json,
            generated_from=generated_from,
            pinned=pinned,
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE workspace_saved_reports
                SET title = ?, summary = ?, export_markdown = ?, export_text = ?,
                    report_json = ?, generated_from_json = ?, updated_at = ?, pinned_at = ?
                WHERE id = ? AND workspace_id = ?
                """,
                (
                    updated.title,
                    updated.summary,
                    updated.export_markdown,
                    updated.export_text,
                    json.dumps(updated.report_json, sort_keys=True),
                    json.dumps(updated.generated_from, sort_keys=True),
                    updated.updated_at,
                    updated.pinned_at,
                    report_id,
                    workspace_id,
                ),
            )
            connection.commit()
        return updated

    def delete_report(self, workspace_id: str, report_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM workspace_saved_reports WHERE id = ? AND workspace_id = ?",
                (report_id, workspace_id),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "DELETE FROM workspace_saved_reports WHERE id = ? AND workspace_id = ?",
                (report_id, workspace_id),
            )
            connection.commit()
        return True

    def _from_row(self, row: sqlite3.Row) -> SavedWorkspaceReport:
        return SavedWorkspaceReport(
            id=row["id"],
            workspace_id=row["workspace_id"],
            report_type=row["report_type"],
            title=row["title"],
            summary=row["summary"],
            export_markdown=row["export_markdown"],
            export_text=row["export_text"],
            report_json=self._json_object(row["report_json"]),
            generated_from=self._json_list(row["generated_from_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            pinned_at=row["pinned_at"],
        )

    @staticmethod
    def _json_object(value: str | None) -> dict[str, object]:
        if not value:
            return {}
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _json_list(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

    def _connect(self) -> sqlite3.Connection:
        connection = open_sqlite(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
