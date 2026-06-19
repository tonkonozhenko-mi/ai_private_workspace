"""Deterministic Helm chart analyzer.

Groups the files the scanner tagged as ``helm`` by their owning ``Chart.yaml``
directory, then reports each chart's name/version/appVersion, its template count,
its values files (including per-environment ``values-<env>.yaml``) and declared
dependencies. Every finding cites its chart. No LLM, no network.
"""

import posixpath
import re
from dataclasses import dataclass
from typing import Any

import yaml

from app.core.domain.analysis import AnalysisFinding, HelmAnalysisResult, HelmChart
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

_VALUES_RE = re.compile(r"(^|/)values([-.][\w.-]+)?\.ya?ml$", re.IGNORECASE)


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _dirname(path: str) -> str:
    return posixpath.dirname(_posix(path))


@dataclass(frozen=True)
class AnalyzeHelmInput:
    workspace_id: str


class HelmAnalysisWorkspaceNotFoundError(ValueError):
    pass


class HelmAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeHelmUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeHelmInput) -> HelmAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise HelmAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise HelmAnalysisScanRequiredError("Project scan required before analysis")

        all_paths = [_posix(f.path) for f in latest_scan.files]
        chart_files = [p for p in all_paths if posixpath.basename(p) == "Chart.yaml"]

        charts: list[HelmChart] = []
        findings: list[AnalysisFinding] = []

        for chart_file in chart_files:
            chart_dir = _dirname(chart_file)
            content = self.file_system.read_text_file(
                root_path=workspace.project_path,
                relative_path=chart_file,
            )
            try:
                parsed = yaml.safe_load(content) or {}
            except yaml.YAMLError as exc:
                findings.append(self._parse_error_finding(chart_file, str(exc)))
                continue
            if not isinstance(parsed, dict):
                parsed = {}

            owned = [p for p in all_paths if p == chart_file or p.startswith(chart_dir + "/")]
            templates = [
                p
                for p in owned
                if "/templates/" in p and posixpath.splitext(p)[1].lower() in {".yaml", ".yml", ".tpl"}
            ]
            value_files = sorted(
                p for p in owned if _VALUES_RE.search(posixpath.basename(p)) or _VALUES_RE.search(p)
            )
            chart = HelmChart(
                name=parsed.get("name") if isinstance(parsed.get("name"), str) else posixpath.basename(chart_dir) or "(chart)",
                version=parsed.get("version") if isinstance(parsed.get("version"), str) else None,
                app_version=parsed.get("appVersion") if isinstance(parsed.get("appVersion"), str) else None,
                chart_path=chart_dir,
                chart_file=chart_file,
                has_values=any(posixpath.basename(p).lower() in {"values.yaml", "values.yml"} for p in value_files),
                templates_count=len(templates),
                value_files=value_files,
                dependencies=self._parse_dependencies(parsed),
            )
            charts.append(chart)
            findings.extend(self._build_chart_findings(chart))

        if not chart_files:
            findings.append(
                AnalysisFinding(
                    id="helm_no_charts",
                    title="No Helm charts found",
                    description="The latest project scan did not detect a Helm Chart.yaml.",
                    severity="info",
                    evidence=[],
                )
            )

        return HelmAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            charts=charts,
            findings=findings,
        )

    @staticmethod
    def _parse_dependencies(parsed: dict[str, Any]) -> list[str]:
        deps = parsed.get("dependencies")
        if not isinstance(deps, list):
            return []
        names: list[str] = []
        for dep in deps:
            if isinstance(dep, dict) and isinstance(dep.get("name"), str):
                names.append(dep["name"])
        return names

    @staticmethod
    def _parse_error_finding(path: str, error: str) -> AnalysisFinding:
        return AnalysisFinding(
            id="helm_chart_parse_error",
            title="Helm Chart.yaml parse error",
            description=f"Unable to parse Chart.yaml: {error}",
            severity="high",
            evidence=[path],
        )

    @staticmethod
    def _build_chart_findings(chart: HelmChart) -> list[AnalysisFinding]:
        findings: list[AnalysisFinding] = []
        if not chart.has_values:
            findings.append(
                AnalysisFinding(
                    id=f"helm_no_values:{chart.chart_file}",
                    title="Chart has no values.yaml",
                    description=(
                        f"Helm chart '{chart.name}' has no values.yaml; defaults are undocumented "
                        "and harder to override safely."
                    ),
                    severity="low",
                    evidence=[chart.chart_file],
                )
            )
        if chart.version is None:
            findings.append(
                AnalysisFinding(
                    id=f"helm_no_version:{chart.chart_file}",
                    title="Chart version missing",
                    description=f"Helm chart '{chart.name}' does not declare a version in Chart.yaml.",
                    severity="low",
                    evidence=[chart.chart_file],
                )
            )
        if chart.templates_count == 0:
            findings.append(
                AnalysisFinding(
                    id=f"helm_no_templates:{chart.chart_file}",
                    title="Chart has no templates",
                    description=(
                        f"Helm chart '{chart.name}' has no templates/ manifests; it may be a "
                        "library chart or incomplete."
                    ),
                    severity="info",
                    evidence=[chart.chart_file],
                )
            )
        return findings
