from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_workspace_with_scan_returns_project_overview_report(tmp_path) -> None:
    _write_overview_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace['id']}/reports/project-overview"
    )

    assert response.status_code == 200
    report = response.json()
    assert report["workspace_id"] == workspace["id"]
    assert report["title"] == "Project overview: Example Workspace"
    assert "scanned files" in report["summary"]
    assert {
        "latest_project_scan",
        "analysis_summary",
        "deterministic_rules",
    }.issubset(set(report["generated_from"]))


def test_project_overview_report_includes_detected_technologies(tmp_path) -> None:
    _write_overview_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace['id']}/reports/project-overview"
    )

    assert response.status_code == 200
    technologies = _section(response.json(), "Detected technologies")
    technology_text = " ".join(technologies["bullets"])
    assert "devops:" in technology_text
    assert "Terraform" in technology_text
    assert "Terragrunt" in technology_text
    assert "GitLab CI" in technology_text
    assert "GitHub Actions" in technology_text
    assert "Python" in technology_text
    assert "Documentation" in technology_text


def test_project_overview_report_includes_infrastructure_and_cicd_sections(
    tmp_path,
) -> None:
    _write_overview_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace['id']}/reports/project-overview"
    )

    assert response.status_code == 200
    infrastructure = _section(response.json(), "Infrastructure")
    infrastructure_text = " ".join(infrastructure["bullets"])
    assert "Terraform" in infrastructure_text
    assert "Terragrunt" in infrastructure_text
    assert "Kubernetes" in infrastructure_text
    assert "Helm" in infrastructure_text

    cicd = _section(response.json(), "CI/CD")
    cicd_text = " ".join(cicd["bullets"])
    assert "GitLab CI" in cicd_text
    assert "GitHub Actions" in cicd_text


def test_project_overview_report_includes_findings_and_next_steps(tmp_path) -> None:
    _write_overview_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(
        f"/workspaces/{workspace['id']}/reports/project-overview"
    )

    assert response.status_code == 200
    findings = _section(response.json(), "Findings")
    assert "Deterministic analyzers reported" in findings["content"]
    assert any("medium:" in bullet or "high:" in bullet for bullet in findings["bullets"])

    next_steps = _section(response.json(), "Recommended next steps")
    assert "Review infrastructure configuration and state management." in next_steps[
        "bullets"
    ]
    assert "Review CI/CD workflow structure and permissions." in next_steps["bullets"]

    suggested_commands = _section(response.json(), "Suggested commands")
    assert any("git status" in bullet for bullet in suggested_commands["bullets"])


def test_project_overview_report_without_scan_returns_400(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(
        f"/workspaces/{workspace['id']}/reports/project-overview"
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Project scan required before generating project overview report"
    )


def test_project_overview_report_unknown_workspace_returns_404() -> None:
    response = client.get("/workspaces/missing-workspace/reports/project-overview")

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


def _write_overview_project(root: Path) -> None:
    _write_text(root / "main.tf", 'resource "null_resource" "example" {}')
    _write_text(
        root / "terragrunt.hcl",
        """
include {
  path = find_in_parent_folders()
}

dependency "network" {
  config_path = "../network"
}

terraform {
  source = "../modules/app"
}

inputs = {
  name = "example"
}
""".strip(),
    )
    _write_text(root / "app.py", "print('hello')")
    _write_text(root / "README.md", "# Example Project")
    _write_text(
        root / ".gitlab-ci.yml",
        """
stages:
  - test

test:
  stage: test
  script:
    - echo test
""".strip(),
    )
    _write_text(
        root / ".github" / "workflows" / "ci.yml",
        """
name: CI
on:
  push:

permissions: read-all

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12"]
    steps:
      - uses: actions/checkout@v4
      - run: echo test
""".strip(),
    )
    _write_text(root / "chart" / "Chart.yaml", "apiVersion: v2\nname: example\n")
    _write_text(
        root / "chart" / "templates" / "deployment.yaml",
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example
""".strip(),
    )


def _section(report: dict, title: str) -> dict:
    for section in report["sections"]:
        if section["title"] == title:
            return section
    raise AssertionError(f"Section not found: {title}")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_workspace_report_catalog_lists_documentation_templates(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/reports/catalog")

    assert response.status_code == 200
    catalog = response.json()
    template_ids = {template["id"] for template in catalog["templates"]}
    assert "project_overview" in template_ids
    assert "onboarding_guide" in template_ids
    assert "devops_review" in template_ids
    assert any("explicit user action" in note for note in catalog["safety_notes"])


def test_workspace_report_template_generates_markdown_and_safety_note(tmp_path) -> None:
    _write_overview_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    response = client.get(f"/workspaces/{workspace['id']}/reports/devops-review")

    assert response.status_code == 200
    report = response.json()
    assert report["report_type"] == "devops_review"
    assert report["title"].startswith("DevOps review")
    assert "read-only" in report["safety_note"]
    assert "# DevOps review" in report["export_markdown"]
    assert "report_template:devops_review" in report["generated_from"]
    assert _section(report, "Infrastructure")
    assert _section(report, "CI/CD")


def test_unknown_workspace_report_template_returns_404(tmp_path) -> None:
    workspace = _create_workspace(tmp_path)

    response = client.get(f"/workspaces/{workspace['id']}/reports/missing-report")

    assert response.status_code == 404
    assert "Unknown report type" in response.json()["detail"]


def test_save_list_pin_update_and_delete_generated_report(tmp_path) -> None:
    _write_overview_project(tmp_path)
    workspace = _create_workspace(tmp_path)
    scan_response = client.post(f"/workspaces/{workspace['id']}/scan")
    assert scan_response.status_code == 200

    save_response = client.post(f"/workspaces/{workspace['id']}/reports/devops-review/save")

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["report_type"] == "devops_review"
    assert saved["export_markdown"].startswith("# DevOps review")
    assert saved["export_text"].startswith("DevOps review")
    assert saved["report_json"]["report_type"] == "devops_review"
    assert saved["is_pinned"] is False

    list_response = client.get(f"/workspaces/{workspace['id']}/reports/saved?search=devops")
    assert list_response.status_code == 200
    assert [report["id"] for report in list_response.json()] == [saved["id"]]

    update_response = client.patch(
        f"/workspaces/{workspace['id']}/reports/saved/{saved['id']}",
        json={"title": "Sprint DevOps Review"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Sprint DevOps Review"

    pin_response = client.patch(
        f"/workspaces/{workspace['id']}/reports/saved/{saved['id']}/pin",
        json={"pinned": True},
    )
    assert pin_response.status_code == 200
    assert pin_response.json()["is_pinned"] is True

    pinned_response = client.get(f"/workspaces/{workspace['id']}/reports/saved?pinned_only=true")
    assert pinned_response.status_code == 200
    assert [report["id"] for report in pinned_response.json()] == [saved["id"]]

    delete_response = client.delete(f"/workspaces/{workspace['id']}/reports/saved/{saved['id']}")
    assert delete_response.status_code == 204

    empty_response = client.get(f"/workspaces/{workspace['id']}/reports/saved")
    assert empty_response.status_code == 200
    assert empty_response.json() == []
