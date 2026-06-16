from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_gitlab_ci_analysis_detects_stages_jobs_and_job_features(tmp_path) -> None:
    _write_text(
        tmp_path / ".gitlab-ci.yml",
        """
        stages:
          - test
          - deploy

        include:
          - local: ci/common.yml

        variables:
          APP_ENV: test
          REGION: us-east-1

        workflow:
          rules:
            - if: $CI_PIPELINE_SOURCE == "push"

        test_app:
          stage: test
          image: python:3.12
          rules:
            - if: $CI_COMMIT_BRANCH
          cache:
            paths:
              - .cache/pip
          artifacts:
            paths:
              - junit.xml

        deploy_app:
          stage: deploy
          needs:
            - test_app
          script:
            - echo deploy
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/gitlab-ci")

    assert response.status_code == 200
    result = response.json()
    assert result["workspace_id"] == workspace["id"]
    assert result["file_path"] == ".gitlab-ci.yml"
    assert result["stages"] == ["test", "deploy"]
    assert result["includes_count"] == 1
    assert result["variables_count"] == 2
    assert result["jobs_count"] == 2

    jobs_by_name = {job["name"]: job for job in result["jobs"]}
    assert jobs_by_name["test_app"]["stage"] == "test"
    assert jobs_by_name["test_app"]["image"] == "python:3.12"
    assert jobs_by_name["test_app"]["has_rules"] is True
    assert jobs_by_name["test_app"]["has_artifacts"] is True
    assert jobs_by_name["test_app"]["has_cache"] is True
    assert jobs_by_name["deploy_app"]["has_needs"] is True

    findings_by_id = {finding["id"]: finding for finding in result["findings"]}
    assert findings_by_id["gitlab_ci_artifacts_detected"]["severity"] == "info"
    assert findings_by_id["gitlab_ci_artifacts_detected"]["evidence"] == ["test_app"]
    assert findings_by_id["gitlab_ci_needs_detected"]["severity"] == "info"
    assert findings_by_id["gitlab_ci_needs_detected"]["evidence"] == ["deploy_app"]


def test_gitlab_ci_only_except_produces_medium_finding(tmp_path) -> None:
    _write_text(
        tmp_path / ".gitlab-ci.yml",
        """
        stages:
          - test

        test_app:
          stage: test
          only:
            - main
          script:
            - echo test
        """,
    )
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/gitlab-ci")

    assert response.status_code == 200
    findings_by_id = {finding["id"]: finding for finding in response.json()["findings"]}
    assert findings_by_id["gitlab_ci_only_except_used"]["severity"] == "medium"
    assert findings_by_id["gitlab_ci_only_except_used"]["evidence"] == ["test_app"]


def test_gitlab_ci_invalid_yaml_returns_high_finding(tmp_path) -> None:
    _write_text(tmp_path / ".gitlab-ci.yml", "stages:\n  - test\ninvalid: [\n")
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/analysis/gitlab-ci")

    assert response.status_code == 200
    result = response.json()
    assert result["file_path"] == ".gitlab-ci.yml"
    assert result["jobs_count"] == 0
    assert result["findings"][0]["id"] == "gitlab_ci_yaml_parse_error"
    assert result["findings"][0]["severity"] == "high"
    assert result["findings"][0]["evidence"] == [".gitlab-ci.yml"]


def test_gitlab_ci_analysis_requires_scan_first(tmp_path) -> None:
    _write_text(tmp_path / ".gitlab-ci.yml", "stages:\n  - test\n")
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/analysis/gitlab-ci")

    assert response.status_code == 400
    assert response.json()["detail"] == "Project scan required before analysis"


def test_gitlab_ci_analysis_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/analysis/gitlab-ci")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def _create_workspace(project_path: Path) -> dict:
    response = client.post(
        "/workspaces",
        json={
            "name": "Example Workspace",
            "project_path": str(project_path),
            "assistant_mode": "local",
            "privacy_mode": "private",
        },
    )

    assert response.status_code == 201
    return response.json()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
