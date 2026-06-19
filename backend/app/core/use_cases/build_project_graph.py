"""Build the Project Intelligence graph for a workspace.

Composes the existing deterministic analyzers (Terraform / Terragrunt / GitLab CI
/ GitHub Actions) into one role-neutral ``ProjectGraph`` and persists it as a
snapshot. Runs only on explicit request; never on startup. Mirrors the analyzer
orchestration in ``get_analysis_summary`` so behaviour stays consistent.
"""

from dataclasses import dataclass

from app.core.domain.project_graph import ProjectSnapshotMeta
from app.core.domain.project_graph_builder import build_project_graph
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.analyze_github_actions import (
    AnalyzeGitHubActionsInput,
    AnalyzeGitHubActionsUseCase,
)
from app.core.use_cases.analyze_gitlab_ci import AnalyzeGitLabCIInput, AnalyzeGitLabCIUseCase
from app.core.use_cases.analyze_helm import AnalyzeHelmInput, AnalyzeHelmUseCase
from app.core.use_cases.analyze_kubernetes import (
    AnalyzeKubernetesInput,
    AnalyzeKubernetesUseCase,
)
from app.core.use_cases.analyze_python import AnalyzePythonInput, AnalyzePythonUseCase
from app.core.use_cases.analyze_references import (
    AnalyzeReferencesInput,
    AnalyzeReferencesUseCase,
)
from app.core.use_cases.analyze_terraform import AnalyzeTerraformInput, AnalyzeTerraformUseCase
from app.core.use_cases.analyze_terragrunt import (
    AnalyzeTerragruntInput,
    AnalyzeTerragruntUseCase,
)


@dataclass(frozen=True)
class BuildProjectGraphInput:
    workspace_id: str


class BuildProjectGraphWorkspaceNotFoundError(ValueError):
    pass


class BuildProjectGraphScanRequiredError(ValueError):
    pass


class BuildProjectGraphUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
        project_graph_repository: ProjectGraphRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.project_graph_repository = project_graph_repository

    def execute(self, request: BuildProjectGraphInput) -> ProjectSnapshotMeta:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise BuildProjectGraphWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise BuildProjectGraphScanRequiredError("Project scan required before analysis")

        detected = {project_file.detected_type for project_file in latest_scan.files}
        skipped: list[str] = []

        def _run(name: str, detected_type: str, run):
            """Run an analyzer only if its files were detected; degrade gracefully."""
            if detected_type not in detected:
                skipped.append(name)
                return None
            try:
                return run()
            except Exception:  # noqa: BLE001 - a failing analyzer must not break the build
                skipped.append(name)
                return None

        ws_id = request.workspace_id
        terraform = _run(
            "terraform",
            "terraform",
            lambda: AnalyzeTerraformUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeTerraformInput(workspace_id=ws_id)),
        )
        terragrunt = _run(
            "terragrunt",
            "terragrunt",
            lambda: AnalyzeTerragruntUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeTerragruntInput(workspace_id=ws_id)),
        )
        gitlab_ci = _run(
            "gitlab_ci",
            "gitlab_ci",
            lambda: AnalyzeGitLabCIUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeGitLabCIInput(workspace_id=ws_id)),
        )
        github_actions = _run(
            "github_actions",
            "github_actions",
            lambda: AnalyzeGitHubActionsUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeGitHubActionsInput(workspace_id=ws_id)),
        )
        kubernetes = _run(
            "kubernetes",
            "kubernetes",
            lambda: AnalyzeKubernetesUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeKubernetesInput(workspace_id=ws_id)),
        )
        helm = _run(
            "helm",
            "helm",
            lambda: AnalyzeHelmUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeHelmInput(workspace_id=ws_id)),
        )
        python = _run(
            "python",
            "python",
            lambda: AnalyzePythonUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzePythonInput(workspace_id=ws_id)),
        )
        # References scan many file types, so it is not gated on one detected
        # type; it still degrades gracefully if it fails.
        try:
            references = AnalyzeReferencesUseCase(
                self.workspace_repository, self.project_scan_repository, self.file_system
            ).execute(AnalyzeReferencesInput(workspace_id=ws_id))
        except Exception:  # noqa: BLE001
            references = None

        graph = build_project_graph(
            ws_id,
            terraform=terraform,
            terragrunt=terragrunt,
            gitlab_ci=gitlab_ci,
            github_actions=github_actions,
            kubernetes=kubernetes,
            helm=helm,
            python=python,
            references=references,
            scan_paths=[project_file.path for project_file in latest_scan.files],
            analyzers_skipped=skipped,
        )
        # A simple scan signature (file count) lets the UI flag a stale snapshot
        # when files change. A content hash can replace this in a later milestone.
        signature = f"files:{len(latest_scan.files)}"
        return self.project_graph_repository.save_graph(graph, scan_signature=signature)
