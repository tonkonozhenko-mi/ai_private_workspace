from app.core.domain.analysis import (
    AnalysisFinding,
    GitHubActionsAnalysisResult,
    GitHubActionsWorkflow,
    GitLabCIAnalysisResult,
    GitLabCIJob,
    TerraformAnalysisResult,
    TerragruntAnalysisResult,
)
from app.core.domain.project_graph import (
    EntityType,
    EvidenceStatus,
    FindingCategory,
    RelationType,
)
from app.core.domain.project_graph_builder import (
    build_project_graph,
    environments_from_paths,
    important_files,
)
from app.core.domain.project_intelligence_view import present_project_intelligence
from app.core.domain.role_lens import Section, role_lens_for


def _terraform() -> TerraformAnalysisResult:
    return TerraformAnalysisResult(
        workspace_id="w1",
        project_path="/p",
        total_terraform_files=3,
        files=[
            "accounts/dev/ca-central-1/app/main.tf",
            "accounts/prod/ca-central-1/app/main.tf",
            "accounts/dev/ca-central-1/app/backend.tf",
        ],
        has_backend_config=True,
        has_provider_config=True,
        has_variables=True,
        has_outputs=True,
        has_modules=True,
        findings=[
            AnalysisFinding(
                id="tf-state",
                title="Local Terraform state",
                description="No remote backend; state stored locally.",
                severity="high",
                evidence=["accounts/dev/ca-central-1/app/backend.tf"],
            )
        ],
    )


def _terragrunt() -> TerragruntAnalysisResult:
    return TerragruntAnalysisResult(
        workspace_id="w1",
        project_path="/p",
        total_terragrunt_files=2,
        files=["accounts/stg/terragrunt.hcl", "accounts/prod/terragrunt.hcl"],
        has_remote_state=True,
        has_include_blocks=True,
        has_dependencies=True,
        has_inputs=True,
        has_terraform_source=True,
        findings=[],
    )


def _gitlab() -> GitLabCIAnalysisResult:
    return GitLabCIAnalysisResult(
        workspace_id="w1",
        project_path="/p",
        file_path=".gitlab-ci.yml",
        stages=["build", "test", "deploy"],
        includes_count=0,
        variables_count=2,
        jobs_count=2,
        jobs=[
            GitLabCIJob("build-image", "build", "docker:24", False, False, True, False, False),
            GitLabCIJob("deploy-prod", "deploy", None, True, False, False, False, True),
        ],
        findings=[
            AnalysisFinding(
                id="latest-tag",
                title="Image uses latest tag",
                description="A job builds with the latest tag.",
                severity="medium",
                evidence=[".gitlab-ci.yml"],
            )
        ],
    )


def _github() -> GitHubActionsAnalysisResult:
    return GitHubActionsAnalysisResult(
        workspace_id="w1",
        project_path="/p",
        workflow_files_count=1,
        workflows=[
            GitHubActionsWorkflow(
                path=".github/workflows/release.yml",
                name="Release",
                triggers=["push"],
                jobs_count=2,
                uses_reusable_workflows=False,
                uses_matrix=True,
                uses_permissions=True,
                has_secrets_reference=True,
            )
        ],
        total_jobs_count=2,
        findings=[],
    )


def test_environments_inferred_from_paths_with_status():
    envs = environments_from_paths(
        ["accounts/dev/x/main.tf", "accounts/prod/y/main.tf", "src/app.py"], "terraform"
    )
    names = {e.name for e in envs}
    assert names == {"dev", "prod"}
    assert all(e.type == EntityType.ENVIRONMENT for e in envs)
    # Environments are inferred from naming, never asserted as confirmed facts.
    assert all(e.status == EvidenceStatus.INFERRED for e in envs)


def test_gitlab_ci_builds_pipeline_jobs_image_relations():
    graph = build_project_graph("w1", gitlab_ci=_gitlab())
    pipelines = graph.entities_of_type(EntityType.PIPELINE)
    jobs = graph.entities_of_type(EntityType.PIPELINE_JOB)
    images = graph.entities_of_type(EntityType.CONTAINER_IMAGE)
    assert len(pipelines) == 1 and len(jobs) == 2 and len(images) == 1
    includes = graph.relations_of_type(RelationType.INCLUDES)
    runs = graph.relations_of_type(RelationType.RUNS)
    assert len(includes) == 2  # pipeline includes both jobs
    assert len(runs) == 1  # build job runs the docker image
    # finding category inferred: "latest tag" -> reliability
    cats = {f.category for f in graph.findings}
    assert FindingCategory.RELIABILITY in cats


def test_build_graph_composes_and_dedups_environments():
    graph = build_project_graph(
        "w1",
        terraform=_terraform(),
        terragrunt=_terragrunt(),
        gitlab_ci=_gitlab(),
        github_actions=_github(),
        analyzers_skipped=["kubernetes"],
    )
    envs = {e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT)}
    # dev+prod from terraform, stg+prod from terragrunt -> prod deduped
    assert envs == {"dev", "prod", "staging"}
    assert set(graph.analyzers_run) == {"terraform", "terragrunt", "gitlab_ci", "github_actions"}
    assert graph.analyzers_skipped == ["kubernetes"]
    infra = {e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT)}
    assert {"Terraform", "Terragrunt"} <= infra
    assert len(graph.entities_of_type(EntityType.PIPELINE)) == 2  # gitlab + github


def test_important_files_scoring_orders_ci_and_infra_first():
    files = [
        ".github/workflows/release.yml",
        "accounts/dev/main.tf",
        "Dockerfile",
        "src/util.py",
        "README.md",
    ]
    ranked = important_files(files)
    paths = [item["path"] for item in ranked]
    assert ".github/workflows/release.yml" in paths
    assert "src/util.py" not in paths  # not a notable file
    # CI workflow scores highest -> appears before README
    assert paths.index(".github/workflows/release.yml") < paths.index("README.md")


def test_role_lens_fallback_and_distinct_orders():
    assert role_lens_for("devops").role == "devops"
    assert role_lens_for("tester").role == "tester"
    assert role_lens_for(None).role == "developer"  # default
    assert role_lens_for("unknown-role").role == "developer"
    # DevOps leads with infrastructure; a tester leads with what might break, not
    # with how it ships (opening on Deployment was the DevOps view in disguise).
    assert role_lens_for("devops").section_order[1] == "infrastructure"
    assert role_lens_for("tester").section_order[1] == "risks"


def test_presenter_projects_sections_with_role_order_and_facts():
    graph = build_project_graph(
        "w1",
        terraform=_terraform(),
        terragrunt=_terragrunt(),
        gitlab_ci=_gitlab(),
        github_actions=_github(),
        scan_paths=["accounts/dev/main.tf", ".github/workflows/release.yml", "Dockerfile"],
    )
    view = present_project_intelligence(graph, role_lens_for("devops"))
    assert view["role"] == "devops"
    assert view["section_order"][1] == Section.INFRASTRUCTURE
    assert "Terraform" in view[Section.SUMMARY]["technology_chips"]
    assert view[Section.SUMMARY]["counts"]["pipelines"] == 2
    assert {"dev", "prod", "staging"} == {
        e["name"] for e in view[Section.ENVIRONMENTS]["environments"]
    }
    # gap-based questions, never asserted defects
    reasons = " ".join(q["reason"] for q in view[Section.QUESTIONS]["questions"])
    assert "rollback" in reasons or "approval" in reasons


def test_presenter_orders_risks_by_role_highlight():
    # A devops lens highlights security/deployment; tester highlights testing.
    graph = build_project_graph("w1", gitlab_ci=_gitlab())
    devops_view = present_project_intelligence(graph, role_lens_for("devops"))
    assert devops_view[Section.RISKS]["highlighted_categories"][0] == "security"
