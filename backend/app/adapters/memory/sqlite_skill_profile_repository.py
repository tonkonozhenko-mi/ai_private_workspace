from datetime import UTC, datetime
from pathlib import Path
import json
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.skill_profile import SkillProfileItem, WorkspaceSkillProfile, normalize_skill_profile


class SQLiteSkillProfileRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def get(self, workspace_id: str) -> WorkspaceSkillProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT workspace_id, profile, skills_json, updated_at
                FROM workspace_skill_profiles
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        skills = [
            SkillProfileItem(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                enabled=bool(item.get("enabled", False)),
                custom_instructions=str(item.get("custom_instructions", "")),
            )
            for item in json.loads(row["skills_json"])
            if isinstance(item, dict)
        ]
        return normalize_skill_profile(
            workspace_id=row["workspace_id"],
            profile=row["profile"],
            skills=skills,
            updated_at=row["updated_at"],
        )

    def save(self, profile: WorkspaceSkillProfile) -> WorkspaceSkillProfile:
        saved = normalize_skill_profile(
            workspace_id=profile.workspace_id,
            profile=profile.profile,
            skills=profile.skills,
            updated_at=profile.updated_at or datetime.now(UTC).isoformat(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_skill_profiles (workspace_id, profile, skills_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    profile = excluded.profile,
                    skills_json = excluded.skills_json,
                    updated_at = excluded.updated_at
                """,
                (
                    saved.workspace_id,
                    saved.profile,
                    json.dumps([
                        {
                            "id": skill.id,
                            "name": skill.name,
                            "enabled": skill.enabled,
                            "custom_instructions": skill.custom_instructions,
                        }
                        for skill in saved.skills
                    ]),
                    saved.updated_at,
                ),
            )
            connection.commit()
        return saved

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
