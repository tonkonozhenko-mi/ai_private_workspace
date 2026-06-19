"""Project Intelligence M2: Kubernetes + Helm analyzers, graph composition and
the role-neutral node/edge projection."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_project_graph_repository import (
    InMemoryProjectGraphRepository,
)
from app.core.domain.project_graph import EntityType, RelationType
from app.core.domain.project_intelligence_view import present_project_graph
from app.core.use_cases.analyze_helm import AnalyzeHelmInput, AnalyzeHelmUseCase
from app.core.use_cases.analyze_kubernetes import (
    AnalyzeKubernetesInput,
    AnalyzeKubernetesUseCase,
)
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphUseCase,
)

_WS = SimpleNamespace(id="w1", project_path="/p")

_K8S_MANIFEST = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: prod
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: api
          image: myrepo/api:latest
---
apiVersion: v1
kind: Service
metadata:
  name: api-svc
  namespace: prod
"""

_CHART = """
name: web
version: 1.2.3
appVersion: "2.0"
"""

_CONTENTS = {
    "deploy/api.yaml": _K8S_MANIFEST,
    "charts/web/Chart.yaml": _CHART,
    "charts/web/values.yaml": "image: web",
    "charts/web/values-staging.yaml": "replicas: 2",
    "charts/web/templates/deployment.yaml": "kind: Deployment",
}


class _WSRepo:
    def get(self, workspace_id):
        return _WS if workspace_id == "w1" else None


class _ScanRepo:
    def __init__(self, files):
        self._scan = SimpleNamespace(
            files=[SimpleNamespace(path=p, detected_type=dt) for p, dt in files]
        )

    def get_latest_scan(self, workspace_id):
        return self._scan


class _FS:
    def read_text_file(self, root_path, relative_path):
        return _CONTENTS.get(relative_path, "")


def _k8s_scan():
    return _ScanRepo([("deploy/api.yaml", "kubernetes")])


def _helm_scan():
    return _ScanRepo(
        [
            ("charts/web/Chart.yaml", "helm"),
            ("charts/web/values.yaml", "yaml"),
            ("charts/web/values-staging.yaml", "yaml"),
            ("charts/web/templates/deployment.yaml", "helm"),
        ]
    )


def test_kubernetes_analyzer_extracts_workload_and_findings():
    result = AnalyzeKubernetesUseCase(_WSRepo(), _k8s_scan(), _FS()).execute(
        AnalyzeKubernetesInput(workspace_id="w1")
    )
    assert result.manifests_count == 1
    assert result.services_count == 1
    assert result.namespaces == ["prod"]
    assert len(result.workloads) == 1
    workload = result.workloads[0]
    assert workload.name == "api"
    assert workload.kind == "Deployment"
    assert workload.images == ["myrepo/api:latest"]
    assert workload.replicas == 1
    assert workload.has_resource_limits is False
    ids = {f.id.split(":")[0] for f in result.findings}
    assert "kubernetes_mutable_image_tag" in ids
    assert "kubernetes_no_resource_limits" in ids
    assert "kubernetes_missing_probes" in ids
    assert "kubernetes_single_replica" in ids


def test_helm_analyzer_groups_chart_and_values():
    result = AnalyzeHelmUseCase(_WSRepo(), _helm_scan(), _FS()).execute(
        AnalyzeHelmInput(workspace_id="w1")
    )
    assert len(result.charts) == 1
    chart = result.charts[0]
    assert chart.name == "web"
    assert chart.version == "1.2.3"
    assert chart.app_version == "2.0"
    assert chart.has_values is True
    assert chart.templates_count == 1
    assert any(p.endswith("values-staging.yaml") for p in chart.value_files)


def test_build_composes_kubernetes_and_helm_graph():
    scan = _ScanRepo(
        [
            ("deploy/api.yaml", "kubernetes"),
            ("charts/web/Chart.yaml", "helm"),
            ("charts/web/values.yaml", "yaml"),
            ("charts/web/values-staging.yaml", "yaml"),
            ("charts/web/templates/deployment.yaml", "helm"),
        ]
    )
    repo = InMemoryProjectGraphRepository()
    uc = BuildProjectGraphUseCase(_WSRepo(), scan, _FS(), repo)
    meta = uc.execute(BuildProjectGraphInput(workspace_id="w1"))
    assert "kubernetes" in meta.analyzers_run
    assert "helm" in meta.analyzers_run

    graph = repo.get_latest_graph("w1")
    infra = sorted(e.name for e in graph.entities_of_type(EntityType.INFRA_COMPONENT))
    assert "Kubernetes" in infra and "Helm" in infra
    services = sorted(e.name for e in graph.entities_of_type(EntityType.SERVICE))
    assert "api" in services and "web" in services
    images = [e.name for e in graph.entities_of_type(EntityType.CONTAINER_IMAGE)]
    assert "myrepo/api:latest" in images
    envs = sorted(e.name for e in graph.entities_of_type(EntityType.ENVIRONMENT))
    # prod from the namespace, staging from values-staging.yaml.
    assert "prod" in envs and "staging" in envs
    deploys = [r for r in graph.relations if r.relation_type == RelationType.DEPLOYS]
    assert deploys, "expected DEPLOYS relations from platforms to services"


def test_present_project_graph_projects_nodes_and_edges():
    scan = _k8s_scan()
    repo = InMemoryProjectGraphRepository()
    BuildProjectGraphUseCase(_WSRepo(), scan, _FS(), repo).execute(
        BuildProjectGraphInput(workspace_id="w1")
    )
    graph = repo.get_latest_graph("w1")
    projected = present_project_graph(graph)
    assert {"nodes", "edges"} <= projected.keys()
    node_ids = {n["id"] for n in projected["nodes"]}
    for edge in projected["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids
    assert any(n["type"] == EntityType.SERVICE for n in projected["nodes"])
