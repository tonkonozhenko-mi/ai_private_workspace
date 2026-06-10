from fastapi.testclient import TestClient

from app.main import app


def test_workspace_skill_profile_defaults_and_save() -> None:
    client = TestClient(app)
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Project",
            "project_path": "/tmp/skill-profile-project",
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()
    workspace_id = created["id"]

    default_response = client.get(f"/workspaces/{workspace_id}/skill-profile")
    assert default_response.status_code == 200
    default_body = default_response.json()
    assert default_body["source"] == "default"
    assert default_body["enabled_skills_count"] == 1

    save_response = client.put(
        f"/workspaces/{workspace_id}/skill-profile",
        json={
            "profile": "workspace",
            "skills": [
                {
                    "id": "developer",
                    "name": "Developer",
                    "enabled": True,
                    "custom_instructions": "Focus on source code and tests.",
                },
                {
                    "id": "devops",
                    "name": "DevOps",
                    "enabled": False,
                    "custom_instructions": "Focus on infrastructure.",
                },
            ],
        },
    )
    assert save_response.status_code == 200
    saved_body = save_response.json()
    assert saved_body["source"] == "saved"
    assert saved_body["enabled_skills_count"] == 1
    developer = next(skill for skill in saved_body["skills"] if skill["id"] == "developer")
    assert developer["enabled"] is True
    assert developer["custom_instructions"] == "Focus on source code and tests."

    reloaded = client.get(f"/workspaces/{workspace_id}/skill-profile").json()
    assert reloaded["source"] == "saved"
    assert reloaded["enabled_skills_count"] == 1


def test_workspace_skill_profile_requires_existing_workspace() -> None:
    client = TestClient(app)

    assert client.get("/workspaces/missing/skill-profile").status_code == 404
    assert client.put(
        "/workspaces/missing/skill-profile",
        json={"profile": "workspace", "skills": []},
    ).status_code == 404
