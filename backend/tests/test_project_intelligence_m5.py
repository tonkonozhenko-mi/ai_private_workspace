"""Project Intelligence M5: cloud catalog, terraform cloud parsing, references,
GitHub Actions jobs, env-token additions, and the cloud/references projections."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_project_graph_repository import (
    InMemoryProjectGraphRepository,
)
from app.core.domain.cloud_catalog import cloud_for_resource
from app.core.domain.project_graph import EntityType, RelationType
from app.core.domain.project_graph_builder import environments_from_paths
from app.core.domain.project_intelligence_view import present_cloud, present_references
from app.core.use_cases.analyze_references import (
    AnalyzeReferencesInput,
    AnalyzeReferencesUseCase,
)
from app.core.use_cases.analyze_terraform import AnalyzeTerraformInput, AnalyzeTerraformUseCase
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphUseCase,
)

_WS = SimpleNamespace(id="w1", project_path="/p")

_MAIN_TF = """
provider "aws" {
  region = "us-east-1"
}
resource "aws_lambda_function" "api" {
  function_name = "api"
}
resource "aws_cloudwatch_event_rule" "schedule" {}
resource "aws_s3_bucket" "state" {}
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
}
variable "x" {}
output "o" {}
"""

_FILES = {
    "accounts/prd/us-east-1/api/main.tf": _MAIN_TF,
    "accounts/prd/us-east-1/api/backend.tf": 'terraform { backend "s3" {} }',
    ".github/workflows/deploy.yaml": (
        "name: Deploy\n"
        "on: [push]\n"
        "permissions:\n  contents: read\n"
        "jobs:\n"
        "  plan:\n    runs-on: ubuntu-latest\n    steps: [{run: terragrunt plan}]\n"
        "  apply:\n    runs-on: ubuntu-latest\n    steps: [{run: terragrunt apply}]\n"
    ),
    "README.md": "See https://docs.example-internal.io/guide and https://github.com/acme/infra",
}


def _scan():
    return SimpleNamespace(
        files=[
            SimpleNamespace(path="accounts/prd/us-east-1/api/main.tf", detected_type="terraform"),
            SimpleNamespace(
                path="accounts/prd/us-east-1/api/backend.tf", detected_type="terraform"
            ),
            SimpleNamespace(path=".github/workflows/deploy.yaml", detected_type="github_actions"),
            SimpleNamespace(path="README.md", detected_type="markdown"),
        ]
    )


class _WSRepo:
    def get(self, workspace_id):
        return _WS if workspace_id == "w1" else None


class _ScanRepo:
    def get_latest_scan(self, workspace_id):
        return _scan()


class _FS:
    def read_text_file(self, root_path, relative_path):
        return _FILES.get(relative_path, "")


def test_cloud_catalog_maps_resources():
    assert cloud_for_resource("aws_lambda_function") == ("AWS", "Lambda")
    assert cloud_for_resource("aws_s3_bucket") == ("AWS", "S3")
    assert cloud_for_resource("aws_cloudwatch_event_rule") == ("AWS", "EventBridge")
    assert cloud_for_resource("google_storage_bucket") == ("Google Cloud", "Cloud Storage")
    assert cloud_for_resource("notacloud_thing") is None


def test_terraform_analyzer_extracts_providers_and_resources():
    result = AnalyzeTerraformUseCase(_WSRepo(), _ScanRepo(), _FS()).execute(
        AnalyzeTerraformInput(workspace_id="w1")
    )
    assert "aws" in result.providers
    types = {r.resource_type for r in result.cloud_resources}
    assert {"aws_lambda_function", "aws_s3_bucket", "aws_cloudwatch_event_rule"} <= types
    assert any(p.endswith("main.tf") for p in result.root_files)


def test_prd_environment_token_now_inferred():
    envs = {
        e.name for e in environments_from_paths(["accounts/prd/us-east-1/api/main.tf"], "terraform")
    }
    assert "prod" in envs


def test_references_analyzer_collects_urls_and_module_sources():
    result = AnalyzeReferencesUseCase(_WSRepo(), _ScanRepo(), _FS()).execute(
        AnalyzeReferencesInput(workspace_id="w1")
    )
    urls = {r.value for r in result.references if r.kind == "url"}
    assert any("github.com/acme/infra" in u for u in urls)
    sources = {r.value for r in result.references if r.kind == "module_source"}
    assert "terraform-aws-modules/vpc/aws" in sources


def test_build_graph_cloud_jobs_references_and_projections():
    repo = InMemoryProjectGraphRepository()
    BuildProjectGraphUseCase(_WSRepo(), _ScanRepo(), _FS(), repo).execute(
        BuildProjectGraphInput(workspace_id="w1")
    )
    graph = repo.get_latest_graph("w1")

    # Cloud services + PROVISIONS relations.
    cloud = {e.name for e in graph.entities_of_type(EntityType.CLOUD_SERVICE)}
    assert any("Lambda" in c for c in cloud) and any("S3" in c for c in cloud)
    assert graph.relations_of_type(RelationType.PROVISIONS)

    # GitHub Actions jobs became pipeline_job entities.
    jobs = {j.name for j in graph.entities_of_type(EntityType.PIPELINE_JOB)}
    assert {"plan", "apply"} <= jobs

    # Terraform connects to the prd→prod environment (map is no longer disconnected).
    assert graph.relations_of_type(RelationType.CONFIGURES)
    envs = {e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT)}
    assert "prod" in envs

    cloud_view = present_cloud(graph)
    assert cloud_view["total_services"] >= 2
    assert any(p["provider"] == "AWS" for p in cloud_view["providers"])

    refs_view = present_references(graph)
    assert refs_view["total"] >= 1
