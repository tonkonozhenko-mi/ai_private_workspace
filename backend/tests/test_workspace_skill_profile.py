from fastapi.testclient import TestClient

from app.main import app


def test_workspace_skill_profile_defaults_and_save(tmp_path) -> None:
    client = TestClient(app)
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Project",
            "project_path": str(tmp_path),
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


def test_every_offered_role_survives_a_save_round_trip(tmp_path) -> None:
    """Through the real endpoint, one role at a time, the way a person does it.

    The domain test pins the normalisation; this pins the whole path — request
    schema, normalisation, storage, and the read-back Settings does on open.
    Four of these six used to come back off.
    """
    client = TestClient(app)
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Round Trip",
            "project_path": str(tmp_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()
    workspace_id = created["id"]
    roles = ["developer", "devops", "tester", "business_analyst", "manager", "dba"]

    for role in roles:
        save = client.put(
            f"/workspaces/{workspace_id}/skill-profile",
            json={
                "profile": "workspace",
                "skills": [
                    {
                        "id": candidate,
                        "name": candidate,
                        "enabled": candidate == role,
                        "custom_instructions": f"Guidance for {candidate}.",
                    }
                    for candidate in roles
                ],
            },
        )
        assert save.status_code == 200, role

        reloaded = client.get(f"/workspaces/{workspace_id}/skill-profile").json()
        enabled = [skill["id"] for skill in reloaded["skills"] if skill["enabled"]]
        assert enabled == [role], f"{role} did not stay switched on"


def test_a_skill_the_server_cannot_place_is_refused_out_loud(tmp_path) -> None:
    # The old behaviour for an unrecognised id was to drop it and answer 200,
    # which is how four roles could fail to save with nothing to show for it.
    client = TestClient(app)
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Unknown Id",
            "project_path": str(tmp_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()

    response = client.put(
        f"/workspaces/{created['id']}/skill-profile",
        json={
            "profile": "workspace",
            "skills": [
                {
                    "id": "astrologer",
                    "name": "Astrologer",
                    "enabled": True,
                    "custom_instructions": "Read the stars.",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "astrologer" in response.json()["detail"]


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


def test_workspace_skill_profile_save_adds_activity_event(tmp_path) -> None:
    client = TestClient(app)
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Activity Project",
            "project_path": str(tmp_path),
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


def test_a_question_that_names_no_instruction_gets_none(tmp_path) -> None:
    """Silence in the request has to survive as silence in the prompt.

    It used not to. An empty ``skill_context`` took the same branch as a request
    with no field at all, and both fell back to the workspace's saved profile —
    which is written from the project's role every time the role changes. The
    role therefore reached the prompt twice: once as "You are reviewing this
    project as a DevOps engineer", and once below it as an instruction, under a
    heading saying the person chose it for this question, followed by a sentence
    about which of the two wins where they disagree. Both were the role.

    It also made the composer's "None" unreachable: the way out of an
    instruction led back to the same one. So the fallback is gone, and this test
    is what notices if it comes back.
    """
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

    # A saved profile exists and is deliberately not what the answer uses.
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
                    }
                ],
            },
        ).status_code
        == 200
    )
    assert client.post(f"/workspaces/{workspace_id}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace_id}/index").status_code == 200

    # An empty list, which is what the composer's "None" sends — and the exact
    # value that used to take the same branch as no field at all.
    response = client.post(
        f"/workspaces/{workspace_id}/ask",
        json={"question": "Explain skillprofiltoken", "limit": 3, "skill_context": []},
    )

    assert response.status_code == 200
    skill_profile = response.json()["skill_profile"]
    assert skill_profile["source"] == "none"
    assert skill_profile["profile"] == "none"
    assert skill_profile["guidance_count"] == 0
    assert skill_profile["active_skills"] == []

    question_event = next(
        event
        for event in client.get(f"/workspaces/{workspace_id}/timeline").json()
        if event["event_type"] == "workspace_question_asked"
    )
    assert question_event["metadata"]["skill_profile_source"] == "none"
    assert question_event["metadata"]["guidance_count"] == "0"


def test_an_instruction_in_the_request_is_the_one_that_is_applied(tmp_path) -> None:
    client = TestClient(app)
    readme = tmp_path / "README.md"
    readme.write_text("skillprofiltoken explains the project.", encoding="utf-8")
    created = client.post(
        "/workspaces",
        json={
            "name": "Skill Profile Request Project",
            "project_path": str(tmp_path),
            "assistant_mode": "devops",
            "privacy_mode": "local_only",
        },
    ).json()
    workspace_id = created["id"]
    assert client.post(f"/workspaces/{workspace_id}/scan").status_code == 200
    assert client.post(f"/workspaces/{workspace_id}/index").status_code == 200

    response = client.post(
        f"/workspaces/{workspace_id}/ask",
        json={
            "question": "Explain skillprofiltoken",
            "limit": 3,
            # An id of the person's own making: instructions are not roles, so
            # nothing here is checked against the canonical six.
            "skill_context": [
                {
                    "id": "custom-7f2",
                    "name": "Security reviewer",
                    "custom_instructions": "Lead with secrets handling.",
                }
            ],
        },
    )

    assert response.status_code == 200
    skill_profile = response.json()["skill_profile"]
    assert skill_profile["source"] == "request"
    assert skill_profile["profile"] == "temporary"
    assert skill_profile["guidance_count"] == 1
    assert skill_profile["active_skills"] == ["Security reviewer"]
