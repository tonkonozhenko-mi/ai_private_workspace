"""Deterministic Kubernetes manifest analyzer.

Parses the YAML manifests the scanner tagged as ``kubernetes`` (possibly
multi-document) and extracts workloads, their container images, replicas,
resource limits and health probes — plus Service / Ingress counts and
namespaces. Every finding cites the file it came from. No LLM, no network.
"""

from dataclasses import dataclass
from typing import Any

import yaml

from app.core.domain.analysis import (
    AnalysisFinding,
    KubernetesAnalysisResult,
    KubernetesWorkload,
)
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

_WORKLOAD_KINDS = {
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "ReplicaSet",
    "Job",
    "CronJob",
    "Pod",
}


@dataclass(frozen=True)
class AnalyzeKubernetesInput:
    workspace_id: str


class KubernetesAnalysisWorkspaceNotFoundError(ValueError):
    pass


class KubernetesAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeKubernetesUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeKubernetesInput) -> KubernetesAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise KubernetesAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise KubernetesAnalysisScanRequiredError("Project scan required before analysis")

        manifest_files = [
            project_file
            for project_file in latest_scan.files
            if project_file.detected_type == "kubernetes"
        ]

        workloads: list[KubernetesWorkload] = []
        findings: list[AnalysisFinding] = []
        namespaces: set[str] = set()
        kinds: set[str] = set()
        services_count = 0
        ingress_count = 0

        for manifest_file in manifest_files:
            content = self.file_system.read_text_file(
                root_path=workspace.project_path,
                relative_path=manifest_file.path,
            )
            try:
                documents = list(yaml.safe_load_all(content))
            except yaml.YAMLError as exc:
                findings.append(self._parse_error_finding(manifest_file.path, str(exc)))
                continue

            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                kind = doc.get("kind")
                if not isinstance(kind, str):
                    continue
                kinds.add(kind)
                metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                namespace = metadata.get("namespace") if isinstance(metadata, dict) else None
                if isinstance(namespace, str) and namespace:
                    namespaces.add(namespace)

                if kind == "Service":
                    services_count += 1
                    continue
                if kind == "Ingress":
                    ingress_count += 1
                    continue
                if kind in _WORKLOAD_KINDS:
                    workload = self._parse_workload(
                        kind=kind,
                        doc=doc,
                        metadata=metadata,
                        namespace=namespace if isinstance(namespace, str) else None,
                        source_file=manifest_file.path,
                    )
                    workloads.append(workload)
                    findings.extend(self._build_workload_findings(workload))

        if not manifest_files:
            findings.append(
                AnalysisFinding(
                    id="kubernetes_no_manifests",
                    title="No Kubernetes manifests found",
                    description="The latest project scan did not detect Kubernetes manifest files.",
                    severity="info",
                    evidence=[],
                )
            )

        return KubernetesAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            manifests_count=len(manifest_files),
            workloads=workloads,
            services_count=services_count,
            ingress_count=ingress_count,
            namespaces=sorted(namespaces),
            kinds=sorted(kinds),
            findings=findings,
        )

    @staticmethod
    def _pod_template_spec(kind: str, doc: dict[str, Any]) -> dict[str, Any]:
        """Return the pod spec for any workload kind, normalising the nesting."""
        spec = doc.get("spec") if isinstance(doc.get("spec"), dict) else {}
        if kind == "Pod":
            return spec
        if kind == "CronJob":
            job = spec.get("jobTemplate") if isinstance(spec.get("jobTemplate"), dict) else {}
            job_spec = job.get("spec") if isinstance(job.get("spec"), dict) else {}
            template = (
                job_spec.get("template") if isinstance(job_spec.get("template"), dict) else {}
            )
            return template.get("spec") if isinstance(template.get("spec"), dict) else {}
        template = spec.get("template") if isinstance(spec.get("template"), dict) else {}
        return template.get("spec") if isinstance(template.get("spec"), dict) else {}

    @classmethod
    def _parse_workload(
        cls,
        kind: str,
        doc: dict[str, Any],
        metadata: dict[str, Any],
        namespace: str | None,
        source_file: str,
    ) -> KubernetesWorkload:
        spec = doc.get("spec") if isinstance(doc.get("spec"), dict) else {}
        name = metadata.get("name") if isinstance(metadata.get("name"), str) else "(unnamed)"
        replicas = spec.get("replicas") if isinstance(spec.get("replicas"), int) else None

        pod_spec = cls._pod_template_spec(kind, doc)
        containers = pod_spec.get("containers")
        container_list = (
            [c for c in containers if isinstance(c, dict)] if isinstance(containers, list) else []
        )

        images = [c["image"] for c in container_list if isinstance(c.get("image"), str)]
        has_limits = any(
            isinstance(c.get("resources"), dict)
            and isinstance(c["resources"].get("limits"), dict)
            and bool(c["resources"]["limits"])
            for c in container_list
        )
        has_liveness = any("livenessProbe" in c for c in container_list)
        has_readiness = any("readinessProbe" in c for c in container_list)

        return KubernetesWorkload(
            name=name,
            kind=kind,
            namespace=namespace,
            images=images,
            replicas=replicas,
            has_resource_limits=has_limits,
            has_liveness_probe=has_liveness,
            has_readiness_probe=has_readiness,
            source_file=source_file,
        )

    @staticmethod
    def _parse_error_finding(path: str, error: str) -> AnalysisFinding:
        return AnalysisFinding(
            id="kubernetes_yaml_parse_error",
            title="Kubernetes YAML parse error",
            description=f"Unable to parse Kubernetes manifest: {error}",
            severity="high",
            evidence=[path],
        )

    @staticmethod
    def _build_workload_findings(workload: KubernetesWorkload) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        ref = f"{workload.kind} '{workload.name}'"

        untagged = [
            img
            for img in workload.images
            if ":" not in img.rsplit("/", 1)[-1] or img.endswith(":latest")
        ]
        if untagged:
            findings.append(
                AnalysisFinding(
                    id=f"kubernetes_mutable_image_tag:{workload.source_file}:{workload.name}",
                    title="Mutable container image tag",
                    description=(
                        f"{ref} uses an image without a fixed version tag "
                        f"({', '.join(untagged)}). Mutable tags like 'latest' make deploys "
                        "non-reproducible."
                    ),
                    severity="medium",
                    evidence=[workload.source_file],
                )
            )

        if (
            workload.kind in {"Deployment", "StatefulSet", "DaemonSet", "Pod"}
            and not workload.has_resource_limits
        ):
            findings.append(
                AnalysisFinding(
                    id=f"kubernetes_no_resource_limits:{workload.source_file}:{workload.name}",
                    title="No resource limits set",
                    description=f"{ref} does not declare CPU/memory limits; a single pod can exhaust the node.",
                    severity="medium",
                    evidence=[workload.source_file],
                )
            )

        if workload.kind in {"Deployment", "StatefulSet"} and not (
            workload.has_liveness_probe and workload.has_readiness_probe
        ):
            missing = []
            if not workload.has_liveness_probe:
                missing.append("liveness")
            if not workload.has_readiness_probe:
                missing.append("readiness")
            findings.append(
                AnalysisFinding(
                    id=f"kubernetes_missing_probes:{workload.source_file}:{workload.name}",
                    title="Health probes missing",
                    description=(
                        f"{ref} is missing {' and '.join(missing)} probe(s); "
                        "Kubernetes cannot tell when the workload is unhealthy or ready."
                    ),
                    severity="low",
                    evidence=[workload.source_file],
                )
            )

        if workload.kind == "Deployment" and workload.replicas == 1:
            findings.append(
                AnalysisFinding(
                    id=f"kubernetes_single_replica:{workload.source_file}:{workload.name}",
                    title="Single replica",
                    description=f"{ref} runs a single replica; there is no redundancy if the pod fails.",
                    severity="low",
                    evidence=[workload.source_file],
                )
            )

        return findings
