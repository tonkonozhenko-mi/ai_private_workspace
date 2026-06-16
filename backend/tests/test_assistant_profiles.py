from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_assistant_profiles_returns_expected_profiles() -> None:
    response = client.get("/assistant-profiles")

    assert response.status_code == 200
    profiles = response.json()
    assert [profile["id"] for profile in profiles] == [
        "devops",
        "developer",
        "documentation",
        "support_incident",
        "manager_summary",
        "tester",
        "business_analyst",
    ]
    devops = _profile(profiles, "devops")
    assert devops["name"] == "DevOps Assistant"
    assert {
        "project_scan",
        "deterministic_analysis",
        "terraform_analysis",
        "terragrunt_analysis",
        "cicd_analysis",
        "command_suggestions",
        "command_approval",
        "workspace_ask",
    }.issubset(devops["primary_capabilities"])
    assert devops["recommended_runtime"] == {
        "VECTOR_STORE": "qdrant",
        "EMBEDDING_PROVIDER": "ollama",
        "LLM_PROVIDER": "ollama",
    }


def test_workspace_recommendation_uses_assistant_mode_and_requires_scan(
    tmp_path,
) -> None:
    workspace = _create_workspace(tmp_path, assistant_mode="devops")

    response = client.get(
        f"/workspaces/{workspace['id']}/assistant-recommendation"
    )

    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["assistant_mode"] == "devops"
    assert recommendation["profile"]["id"] == "devops"
    assert recommendation["matched_skills"] == []
    assert recommendation["recommended_actions"][0] == "scan_project"
    assert "workspace_ask" in recommendation["missing_capabilities"]
    assert "real_llm_answers" in recommendation["missing_capabilities"]
    assert "persistent_vector_search" in recommendation["missing_capabilities"]


def test_devops_recommendation_includes_detected_skill_actions(tmp_path) -> None:
    _write_text(
        tmp_path / "main.tf",
        'terraform { backend "s3" {} }\n',
    )
    _write_text(
        tmp_path / "terragrunt.hcl",
        'remote_state { backend = "s3" }\n',
    )
    _write_text(
        tmp_path / ".gitlab-ci.yml",
        "stages:\n  - test\njob:\n  stage: test\n  script: echo test\n",
    )
    workspace = _create_workspace(tmp_path, assistant_mode="devops")
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace['id']}/assistant-recommendation"
    )

    assert response.status_code == 200
    recommendation = response.json()
    assert {"Terraform", "Terragrunt", "GitLab CI"}.issubset(
        recommendation["matched_skills"]
    )
    assert recommendation["recommended_actions"] == [
        "analyze_terraform",
        "analyze_terragrunt",
        "analyze_cicd",
        "index_workspace",
    ]


def test_legacy_local_assistant_mode_uses_developer_profile(tmp_path) -> None:
    workspace = _create_workspace(tmp_path, assistant_mode="local")

    response = client.get(
        f"/workspaces/{workspace['id']}/assistant-recommendation"
    )

    assert response.status_code == 200
    recommendation = response.json()
    assert recommendation["assistant_mode"] == "local"
    assert recommendation["profile"]["id"] == "developer"


def test_workspace_assistant_recommendation_unknown_workspace_returns_404() -> None:
    response = client.get(
        "/workspaces/missing-workspace/assistant-recommendation"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _profile(profiles: list[dict], profile_id: str) -> dict:
    return next(profile for profile in profiles if profile["id"] == profile_id)


def _create_workspace(project_path: Path, assistant_mode: str) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Assistant Profile Workspace",
            "project_path": str(project_path),
            "assistant_mode": assistant_mode,
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
