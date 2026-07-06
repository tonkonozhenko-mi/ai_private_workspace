"""Deterministic project-type classification (D4)."""

from app.core.domain.project_graph import EntityType, ProjectEntity, ProjectGraph
from app.core.domain.project_type import (
    KIND_APPLICATION,
    KIND_INFRASTRUCTURE,
    KIND_MIXED,
    KIND_UNKNOWN,
    classify_project,
)


def _entity(etype, name, analyzer="a", **meta):
    return ProjectEntity(id=f"{etype}:{name}", type=etype, name=name, analyzer=analyzer, metadata=meta)


def _graph(entities, analyzers):
    return ProjectGraph(workspace_id="w", entities=entities, analyzers_run=analyzers)


def test_pure_terraform_repo_is_infrastructure():
    # A Terraform repo with a single helper .py must NOT read as "Python application".
    entities = [
        _entity(EntityType.INFRA_COMPONENT, "aws_s3_bucket"),
        _entity(EntityType.INFRA_COMPONENT, "aws_iam_role"),
        _entity(EntityType.INFRA_COMPONENT, "aws_lambda_function"),
        _entity(EntityType.PIPELINE, "deploy.yml"),
        _entity(EntityType.APPLICATION, "Python application", modules="1"),  # a stray script
        _entity(EntityType.MODULE, "scripts"),
    ]
    result = classify_project(_graph(entities, ["terraform", "github_actions", "python"]))
    assert result.kind == KIND_INFRASTRUCTURE
    assert result.label == "infrastructure project (Terraform, CI/CD)"


def test_fastapi_app_is_application_by_framework():
    entities = [
        _entity(EntityType.APPLICATION, "FastAPI application", frameworks="FastAPI", modules="12"),
        *[_entity(EntityType.MODULE, f"m{i}") for i in range(12)],
    ]
    result = classify_project(_graph(entities, ["python"]))
    assert result.kind == KIND_APPLICATION
    assert result.label == "FastAPI application"


def test_app_with_deploy_infra_is_mixed_led_by_app():
    entities = [
        _entity(EntityType.APPLICATION, "FastAPI application", frameworks="FastAPI", modules="8"),
        *[_entity(EntityType.MODULE, f"m{i}") for i in range(8)],
        _entity(EntityType.INFRA_COMPONENT, "aws_ecs_service"),
        _entity(EntityType.INFRA_COMPONENT, "aws_rds_instance"),
        _entity(EntityType.PIPELINE, "ci.yml"),
    ]
    result = classify_project(_graph(entities, ["python", "terraform", "github_actions"]))
    assert result.kind == KIND_MIXED
    assert result.label == "FastAPI application"  # led by the app


def test_infra_heavy_but_real_app_is_mixed_led_by_infra():
    entities = [
        _entity(EntityType.APPLICATION, "FastAPI application", frameworks="FastAPI", modules="3"),
        *[_entity(EntityType.MODULE, f"m{i}") for i in range(3)],
        *[_entity(EntityType.INFRA_COMPONENT, f"res{i}") for i in range(12)],
        _entity(EntityType.PIPELINE, "ci.yml"),
    ]
    result = classify_project(_graph(entities, ["python", "terraform", "github_actions"]))
    assert result.kind == KIND_MIXED
    assert "infrastructure project" in result.label  # infra outweighs → led by infra


def test_empty_graph_is_unknown():
    result = classify_project(_graph([], []))
    assert result.kind == KIND_UNKNOWN
    assert result.label == ""


def test_kubernetes_and_helm_named_in_headline():
    entities = [
        _entity(EntityType.INFRA_COMPONENT, "deployment.yaml"),
        _entity(EntityType.INFRA_COMPONENT, "service.yaml"),
    ]
    result = classify_project(_graph(entities, ["kubernetes", "helm"]))
    assert result.kind == KIND_INFRASTRUCTURE
    assert result.label == "infrastructure project (Kubernetes, Helm)"
