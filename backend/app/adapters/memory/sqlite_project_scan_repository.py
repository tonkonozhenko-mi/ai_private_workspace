from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.project_scan import ProjectFile, ProjectScanResult
from app.core.domain.skill import SkillMatch


class SQLiteProjectScanRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save_latest_scan(self, workspace_id: str, scan_result: ProjectScanResult) -> None:
        scan_json = json.dumps(self._to_dict(scan_result))

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_project_scans (
                    workspace_id,
                    scan_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    scan_json = excluded.scan_json,
                    updated_at = excluded.updated_at
                """,
                (
                    workspace_id,
                    scan_json,
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()

    def get_latest_scan(self, workspace_id: str) -> ProjectScanResult | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT scan_json
                FROM workspace_project_scans
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None
        return self._from_dict(json.loads(row["scan_json"]))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_dict(scan_result: ProjectScanResult) -> dict:
        return {
            "project_path": scan_result.project_path,
            "total_files": scan_result.total_files,
            "scanned_files": scan_result.scanned_files,
            "skipped_files": scan_result.skipped_files,
            "total_size_bytes": scan_result.total_size_bytes,
            "detected_skills": [
                {
                    "name": skill.name,
                    "category": skill.category,
                    "confidence": skill.confidence,
                    "evidence": skill.evidence,
                }
                for skill in scan_result.detected_skills
            ],
            "files": [
                {
                    "path": project_file.path,
                    "extension": project_file.extension,
                    "size_bytes": project_file.size_bytes,
                    "detected_type": project_file.detected_type,
                    "modified_at": project_file.modified_at,
                }
                for project_file in scan_result.files
            ],
        }

    @staticmethod
    def _from_dict(data: dict) -> ProjectScanResult:
        return ProjectScanResult(
            project_path=data["project_path"],
            total_files=data["total_files"],
            scanned_files=data["scanned_files"],
            skipped_files=data["skipped_files"],
            total_size_bytes=data["total_size_bytes"],
            detected_skills=[
                SkillMatch(
                    name=skill["name"],
                    category=skill["category"],
                    confidence=skill["confidence"],
                    evidence=list(skill["evidence"]),
                )
                for skill in data["detected_skills"]
            ],
            files=[
                ProjectFile(
                    path=project_file["path"],
                    extension=project_file["extension"],
                    size_bytes=project_file["size_bytes"],
                    detected_type=project_file["detected_type"],
                    modified_at=project_file.get("modified_at"),
                )
                for project_file in data["files"]
            ],
        )
