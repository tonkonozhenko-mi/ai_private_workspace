from fastapi.testclient import TestClient

from app.main import app


def test_workspace_indexing_rules_default_and_update(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (project / "README.md").write_text("docs", encoding="utf-8")

    client = TestClient(app)
    workspace = client.post(
        "/workspaces",
        json={
            "name": "Rules project",
            "project_path": str(project),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()

    default_response = client.get(f"/workspaces/{workspace['id']}/indexing-rules")
    assert default_response.status_code == 200
    default_rules = default_response.json()
    assert default_rules["source"] == "default"
    assert "node_modules/**" in default_rules["exclude_patterns"]

    update_response = client.put(
        f"/workspaces/{workspace['id']}/indexing-rules",
        json={
            "profile": "source-first",
            "include_patterns": ["src/**"],
            "exclude_patterns": ["dist/**"],
        },
    )
    assert update_response.status_code == 200
    saved_rules = update_response.json()
    assert saved_rules["source"] == "saved"
    assert saved_rules["profile"] == "source-first"
    assert saved_rules["include_patterns"] == ["src/**"]

    preview = client.post(f"/workspaces/{workspace['id']}/files/preview").json()
    assert preview["profile"] == "source-first"
    assert preview["include_rules_count"] == 1
    assert preview["exclude_rules_count"] == 1
    assert preview["included_samples"][0]["path"] == "src/app.py"
    assert preview["excluded_files_count"] >= 1


def test_scan_job_uses_saved_indexing_rules(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (project / "README.md").write_text("docs", encoding="utf-8")

    client = TestClient(app)
    workspace = client.post(
        "/workspaces",
        json={
            "name": "Job rules project",
            "project_path": str(project),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()
    client.put(
        f"/workspaces/{workspace['id']}/indexing-rules",
        json={
            "profile": "source-first",
            "include_patterns": ["src/**"],
            "exclude_patterns": [],
        },
    )

    job = client.post(f"/workspaces/{workspace['id']}/jobs/scan").json()
    assert job["request_summary"]["file_rules_profile"] == "source-first"
    assert job["request_summary"]["include_patterns"] == "src/**"
