from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_data_safety_reports_database_location() -> None:
    response = client.get("/runtime/local-data")

    assert response.status_code == 200
    body = response.json()
    assert body["repository"] in {"sqlite", "memory"}
    assert body["database_path"].endswith("workspaces.db")
    assert "backend/.ai-workbench" in body["safe_update_excludes"]
    assert "*.db" in body["safe_update_excludes"]
    assert isinstance(body["backup_hints"], list)



def test_startup_checklist_reports_read_only_steps() -> None:
    response = client.get("/runtime/startup-checklist")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "review", "blocked"}
    assert body["safe_to_continue"] in {True, False}
    assert "frontend only displays" in body["safety_note"].lower()
    item_ids = {item["id"] for item in body["items"]}
    assert {"python", "database", "local-data-protection", "models", "search-context"}.issubset(item_ids)


def test_database_backup_and_migration_endpoints_are_safe() -> None:
    backups_response = client.get("/runtime/database-backups")
    assert backups_response.status_code == 200
    backups_body = backups_response.json()
    assert backups_body["database_path"].endswith("workspaces.db")
    assert "manual" in backups_body["restore_note"].lower()

    migration_response = client.get("/runtime/database-migration-safety")
    assert migration_response.status_code == 200
    migration_body = migration_response.json()
    assert migration_body["status"] in {"ok", "review"}
    assert migration_body["schema_version"] == "sqlite-auto-migrations-v1"
    assert isinstance(migration_body["tables"], list)
    assert "read-only" in migration_body["safety_note"].lower()


def test_restore_plan_rejects_path_traversal() -> None:
    response = client.post(
        "/runtime/database-restore-plan",
        json={"backup_filename": "../workspaces.db"},
    )

    assert response.status_code == 400


def test_runtime_troubleshooting_is_read_only_and_actionable() -> None:
    response = client.get("/runtime/troubleshooting")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "review", "blocked"}
    assert "read-only" in body["safety_note"].lower()
    assert isinstance(body["issues"], list)
    assert body["quick_checks"]
    assert body["safe_restart_commands"]
    assert any("runtime/health" in step["copy_command"] for step in body["quick_checks"] if step["copy_command"])
    assert any("python -m uvicorn" in step["copy_command"] for step in body["safe_restart_commands"] if step["copy_command"])


def test_update_safety_workflow_is_copy_only_and_protects_runtime_data() -> None:
    response = client.get("/runtime/update-safety")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "review"}
    assert "--dry-run" in body["dry_run_command"]
    assert "apply_generated_update.sh" in body["apply_command"]
    assert "backend/.ai-workbench" in body["required_excludes"]
    assert "*.db" in body["required_excludes"]
    assert "read-only" in body["safety_note"].lower()
    assert any("dry-run" in check.lower() for check in body["preflight_checks"])
