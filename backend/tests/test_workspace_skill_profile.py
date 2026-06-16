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
    assert (
        client.put(
            "/workspaces/missing/skill-profile",
            json={"profile": "workspace", "skills": []},
        ).status_code
        == 404
    )


def test_workspace_skill_profile_save_adds_activity_event() -> None:
    client = TestClient(app)
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Activity Project",
            "project_path": "/tmp/skill-profile-activity-project",
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()
    workspace_id = created["id"]

    response = client.put(
        f"/workspaces/{workspace_id}/skill-profile",
        json={
            "profile": "workspace",
            "skills": [
                {
                    "id": "devops",
                    "name": "DevOps",
                    "enabled": True,
                    "custom_instructions": "Focus on infrastructure and deployment safety.",
                },
                {
                    "id": "documentation",
                    "name": "Documentation",
                    "enabled": True,
                    "custom_instructions": "Explain docs gaps clearly.",
                },
            ],
        },
    )

    assert response.status_code == 200
    timeline = client.get(f"/workspaces/{workspace_id}/timeline").json()
    event = next(item for item in timeline if item["event_type"] == "skill_profile_saved")
    assert event["title"] == "Skill profile saved"
    assert event["metadata"]["enabled_skills_count"] == "2"
    assert "DevOps" in event["metadata"]["enabled_skills"]


def test_ask_response_includes_saved_skill_profile_audit(tmp_path) -> None:
    client = TestClient(app)
    readme = tmp_path / "README.md"
    readme.write_text("skillprofiltoken explains the project.", encoding="utf-8")
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Ask Audit Project",
            "project_path": str(tmp_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()
    workspace_id = created["id"]

    assert (
        client.put(
            f"/workspaces/{workspace_id}/skill-profile",
            json={
                "profile": "workspace",
                "skills": [
                    {
                        "id": "documentation",
                        "name": "Documentation",
                        "enabled": True,
                        "custom_instructions": "Focus on documentation quality.",
                    },
                    {
                        "id": "devops",
                        "name": "DevOps",
                        "enabled": False,
                        "custom_instructions": "Focus on infrastructure.",
                    },
                ],
            },
        ).status_code
        == 200
    )
    assert client.post(f"/workspaces/{workspace_id}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace_id}/index").status_code == 200

    response = client.post(
        f"/workspaces/{workspace_id}/ask",
        json={"question": "Explain skillprofiltoken", "limit": 3},
    )

    assert response.status_code == 200
    skill_profile = response.json()["skill_profile"]
    assert skill_profile["source"] == "saved"
    assert skill_profile["profile"] == "workspace"
    assert skill_profile["guidance_count"] == 1
    assert skill_profile["active_skills"] == ["Documentation"]

    question_event = next(
        event
        for event in client.get(f"/workspaces/{workspace_id}/timeline").json()
        if event["event_type"] == "workspace_question_asked"
    )
    assert question_event["metadata"]["skill_profile_source"] == "saved"
    assert question_event["metadata"]["guidance_count"] == "1"
    assert question_event["metadata"]["applied_skills"] == "Documentation"
