"""Project Intelligence M3: deployment-flow derivation, environment comparison,
and the ask-the-graph prompt (deterministic parts only)."""

from app.core.domain.project_graph import (
    Confidence,
    EntityType,
    EvidenceStatus,
    ProjectEntity,
    ProjectGraph,
    ProjectRelation,
    RelationType,
)
from app.core.domain.project_intelligence_flow import (
    compare_environments,
    derive_deployment_flow,
)
from app.core.domain.project_intelligence_prompt import build_ask_graph_prompt
from app.core.domain.project_intelligence_view import present_project_intelligence
from app.core.domain.role_lens import role_lens_for


def _entity(eid, etype, name, **kw):
    return ProjectEntity(id=eid, type=etype, name=name, analyzer=kw.pop("analyzer", "x"), **kw)


def _full_graph() -> ProjectGraph:
    pipeline = _entity("pipeline:ci", EntityType.PIPELINE, "GitLab CI")
    job = _entity("pipeline_job:build", EntityType.PIPELINE_JOB, "build")
    ci_image = _entity("container_image:app", EntityType.CONTAINER_IMAGE, "app:1.0")
    service = _entity("service:api", EntityType.SERVICE, "api")
    runtime_image = _entity("container_image:ext", EntityType.CONTAINER_IMAGE, "ext/db:5")
    env = _entity(
        "environment:prod",
        EntityType.ENVIRONMENT,
        "prod",
        confidence=Confidence.MEDIUM,
        status=EvidenceStatus.INFERRED,
        source_file="k8s/prod/api.yaml",
        metadata={"evidence_paths": "3"},
    )
    platform = _entity("infra_component:kubernetes", EntityType.INFRA_COMPONENT, "Kubernetes")
    return ProjectGraph(
        workspace_id="w1",
        entities=[pipeline, job, ci_image, service, runtime_image, env, platform],
        relations=[
            ProjectRelation("r1", pipeline.id, job.id, RelationType.INCLUDES, "x"),
            ProjectRelation("r2", job.id, ci_image.id, RelationType.RUNS, "x"),
            ProjectRelation("r3", platform.id, service.id, RelationType.DEPLOYS, "x"),
            ProjectRelation("r4", service.id, runtime_image.id, RelationType.RUNS, "x"),
        ],
        analyzers_run=["gitlab_ci", "kubernetes"],
    )


def test_deployment_flow_stages_in_order():
    flow = derive_deployment_flow(_full_graph())
    keys = [s["key"] for s in flow["stages"]]
    assert keys == ["source_ci", "build", "deploy", "environments"]
    counts = {s["key"]: s["count"] for s in flow["stages"]}
    assert counts["source_ci"] == 1
    assert counts["build"] == 2
    assert counts["deploy"] == 1
    assert counts["environments"] == 1


def test_deployment_flow_flags_deployed_image_not_built():
    flow = derive_deployment_flow(_full_graph())
    titles = {g["title"] for g in flow["gaps"]}
    # ext/db:5 is RUN by a service but no CI job builds it.
    assert "Deployed image not built in CI" in titles


def test_deployment_flow_gaps_on_empty_graph():
    empty = ProjectGraph(workspace_id="w1")
    flow = derive_deployment_flow(empty)
    titles = {g["title"] for g in flow["gaps"]}
    assert "No environments inferred" in titles
    assert all(s["count"] == 0 for s in flow["stages"])


def test_compare_environments_summary_and_rows():
    result = compare_environments(_full_graph())
    assert result["has_production"] is True
    assert len(result["environments"]) == 1
    row = result["environments"][0]
    assert row["name"] == "prod"
    assert row["status"] == EvidenceStatus.INFERRED
    assert row["evidence_count"] == 3
    assert "production" in result["summary"].lower()


def test_compare_environments_empty():
    result = compare_environments(ProjectGraph(workspace_id="w1"))
    assert result["environments"] == []
    assert result["has_production"] is False


def test_ask_graph_prompt_constrains_to_facts():
    view = present_project_intelligence(_full_graph(), role_lens_for("devops"))
    prompt = build_ask_graph_prompt(view, "DevOps", "How is prod deployed?")
    assert "How is prod deployed?" in prompt
    assert "ONLY the facts" in prompt
    assert "analyzed files" in prompt
