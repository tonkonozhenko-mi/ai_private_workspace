import sqlite3
from datetime import UTC, datetime

from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.core.domain.workspace import Workspace


def test_create_and_get_workspace(tmp_path) -> None:
    repository = SQLiteWorkspaceRepository(tmp_path / "workspaces.db")
    workspace = Workspace(
        id="workspace-1",
        name="Example Workspace",
        project_path="/tmp/example-project",
        assistant_mode="local",
        privacy_mode="private",
        created_at=datetime.now(UTC),
    )

    created_workspace = repository.create(workspace)
    found_workspace = repository.get(workspace.id)

    assert created_workspace == workspace
    assert found_workspace == workspace


def test_list_workspaces(tmp_path) -> None:
    repository = SQLiteWorkspaceRepository(tmp_path / "workspaces.db")
    first_workspace = Workspace(
        id="workspace-1",
        name="First Workspace",
        project_path="/tmp/first-project",
        assistant_mode="local",
        privacy_mode="private",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second_workspace = Workspace(
        id="workspace-2",
        name="Second Workspace",
        project_path="/tmp/second-project",
        assistant_mode="local",
        privacy_mode="private",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    repository.create(second_workspace)
    repository.create(first_workspace)

    assert repository.list() == [first_workspace, second_workspace]


def test_missing_workspace_returns_none(tmp_path) -> None:
    repository = SQLiteWorkspaceRepository(tmp_path / "workspaces.db")

    assert repository.get("missing-workspace") is None


def test_workspaces_survive_repository_recreation(tmp_path) -> None:
    db_path = tmp_path / "workspaces.db"
    repository = SQLiteWorkspaceRepository(db_path)
    workspace = Workspace(
        id="workspace-1",
        name="Persistent Workspace",
        project_path="/tmp/persistent-project",
        assistant_mode="local",
        privacy_mode="private",
        created_at=datetime.now(UTC),
    )

    repository.create(workspace)
    restarted_repository = SQLiteWorkspaceRepository(db_path)

    assert restarted_repository.get(workspace.id) == workspace


def test_existing_workspace_table_is_migrated_with_archived_at(tmp_path) -> None:
    db_path = tmp_path / "legacy-workspaces.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                project_path TEXT NOT NULL,
                assistant_mode TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO workspaces (
                id, name, project_path, assistant_mode, privacy_mode, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-workspace",
                "Legacy Workspace",
                "/tmp/legacy",
                "local",
                "private",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()

    repository = SQLiteWorkspaceRepository(db_path)
    workspace = repository.get("legacy-workspace")

    assert workspace is not None
    assert workspace.archived_at is None
    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(workspaces)").fetchall()}
    assert "archived_at" in columns
