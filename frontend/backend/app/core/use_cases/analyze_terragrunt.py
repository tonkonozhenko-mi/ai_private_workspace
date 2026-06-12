from dataclasses import dataclass

from app.core.domain.analysis import AnalysisFinding, TerragruntAnalysisResult
from app.core.domain.project_scan import ProjectFile
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class AnalyzeTerragruntInput:
    workspace_id: str


class TerragruntAnalysisWorkspaceNotFoundError(ValueError):
    pass


class TerragruntAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeTerragruntUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeTerragruntInput) -> TerragruntAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise TerragruntAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise TerragruntAnalysisScanRequiredError("Project scan required before analysis")

        terragrunt_files = [
            project_file
            for project_file in latest_scan.files
            if project_file.detected_type == "terragrunt"
        ]
        terragrunt_file_paths = [project_file.path for project_file in terragrunt_files]
        file_contents = {
            project_file.path: self.file_system.read_text_file(
                root_path=workspace.project_path,
                relative_path=project_file.path,
            )
            for project_file in terragrunt_files
        }

        dependency_files = [
            path for path, content in file_contents.items() if 'dependency "' in content
        ]
        input_files = [
            path for path, content in file_contents.items() if "inputs =" in content
        ]
        terraform_source_files = [
            path
            for path, content in file_contents.items()
            if "terraform {" in content and "source =" in content
        ]

        has_remote_state = self._contains_any(file_contents, "remote_state")
        has_include_blocks = self._contains_any(file_contents, "include")
        has_dependencies = bool(dependency_files)
        has_inputs = bool(input_files)
        has_terraform_source = bool(terraform_source_files)

        return TerragruntAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            total_terragrunt_files=len(terragrunt_files),
            files=terragrunt_file_paths,
            has_remote_state=has_remote_state,
            has_include_blocks=has_include_blocks,
            has_dependencies=has_dependencies,
            has_inputs=has_inputs,
            has_terraform_source=has_terraform_source,
            findings=self._build_findings(
                terragrunt_files=terragrunt_files,
                terragrunt_file_paths=terragrunt_file_paths,
                has_remote_state=has_remote_state,
                has_include_blocks=has_include_blocks,
                dependency_files=dependency_files,
                input_files=input_files,
                terraform_source_files=terraform_source_files,
            ),
        )

    @staticmethod
    def _contains_any(file_contents: dict[str, str], needle: str) -> bool:
        return any(needle in content for content in file_contents.values())

    def _build_findings(
        self,
        terragrunt_files: list[ProjectFile],
        terragrunt_file_paths: list[str],
        has_remote_state: bool,
        has_include_blocks: bool,
        dependency_files: list[str],
        input_files: list[str],
        terraform_source_files: list[str],
    ) -> list[AnalysisFinding]:
        if not terragrunt_files:
            return [
                AnalysisFinding(
                    id="terragrunt_no_files",
                    title="No Terragrunt files found",
                    description="The latest project scan did not detect Terragrunt files.",
                    severity="info",
                    evidence=[],
                )
            ]

        findings: list[AnalysisFinding] = []

        if not has_remote_state:
            findings.append(
                AnalysisFinding(
                    id="terragrunt_remote_state_missing",
                    title="Remote state not detected",
                    description="No Terragrunt remote_state block was found.",
                    severity="medium",
                    evidence=terragrunt_file_paths,
                )
            )

        if not has_include_blocks:
            findings.append(
                AnalysisFinding(
                    id="terragrunt_include_missing",
                    title="Include block not detected",
                    description="No Terragrunt include block was found.",
                    severity="low",
                    evidence=terragrunt_file_paths,
                )
            )

        if dependency_files:
            findings.append(
                AnalysisFinding(
                    id="terragrunt_dependencies_detected",
                    title="Dependencies detected",
                    description="Terragrunt dependency blocks were found.",
                    severity="info",
                    evidence=dependency_files,
                )
            )

        if input_files:
            findings.append(
                AnalysisFinding(
                    id="terragrunt_inputs_detected",
                    title="Inputs detected",
                    description="Terragrunt inputs were found.",
                    severity="info",
                    evidence=input_files,
                )
            )

        if terraform_source_files:
            findings.append(
                AnalysisFinding(
                    id="terragrunt_terraform_source_detected",
                    title="Terraform source detected",
                    description="Terragrunt terraform source configuration was found.",
                    severity="info",
                    evidence=terraform_source_files,
                )
            )

        return findings
