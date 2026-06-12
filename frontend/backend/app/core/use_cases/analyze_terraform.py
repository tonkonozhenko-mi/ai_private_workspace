from dataclasses import dataclass

from app.core.domain.analysis import AnalysisFinding, TerraformAnalysisResult
from app.core.domain.project_scan import ProjectFile
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class AnalyzeTerraformInput:
    workspace_id: str


class TerraformAnalysisWorkspaceNotFoundError(ValueError):
    pass


class TerraformAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeTerraformUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeTerraformInput) -> TerraformAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise TerraformAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise TerraformAnalysisScanRequiredError("Project scan required before analysis")

        terraform_files = [
            project_file
            for project_file in latest_scan.files
            if project_file.detected_type == "terraform"
        ]
        terraform_file_paths = [project_file.path for project_file in terraform_files]
        file_contents = {
            project_file.path: self.file_system.read_text_file(
                root_path=workspace.project_path,
                relative_path=project_file.path,
            )
            for project_file in terraform_files
        }

        has_backend_config = self._contains_any(file_contents, 'backend "')
        has_provider_config = self._contains_any(file_contents, 'provider "')
        has_variables = self._contains_any(file_contents, 'variable "')
        has_outputs = self._contains_any(file_contents, 'output "')
        module_files = [
            path for path, content in file_contents.items() if 'module "' in content
        ]
        has_modules = bool(module_files)

        return TerraformAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            total_terraform_files=len(terraform_files),
            files=terraform_file_paths,
            has_backend_config=has_backend_config,
            has_provider_config=has_provider_config,
            has_variables=has_variables,
            has_outputs=has_outputs,
            has_modules=has_modules,
            findings=self._build_findings(
                terraform_files=terraform_files,
                terraform_file_paths=terraform_file_paths,
                has_backend_config=has_backend_config,
                has_provider_config=has_provider_config,
                has_variables=has_variables,
                has_outputs=has_outputs,
                module_files=module_files,
            ),
        )

    @staticmethod
    def _contains_any(file_contents: dict[str, str], needle: str) -> bool:
        return any(needle in content for content in file_contents.values())

    def _build_findings(
        self,
        terraform_files: list[ProjectFile],
        terraform_file_paths: list[str],
        has_backend_config: bool,
        has_provider_config: bool,
        has_variables: bool,
        has_outputs: bool,
        module_files: list[str],
    ) -> list[AnalysisFinding]:
        if not terraform_files:
            return [
                AnalysisFinding(
                    id="terraform_no_files",
                    title="No Terraform files found",
                    description="The latest project scan did not detect Terraform files.",
                    severity="info",
                    evidence=[],
                )
            ]

        findings: list[AnalysisFinding] = []

        if not has_backend_config:
            findings.append(
                AnalysisFinding(
                    id="terraform_backend_missing",
                    title="Backend configuration not detected",
                    description="No Terraform backend block was found in scanned Terraform files.",
                    severity="medium",
                    evidence=terraform_file_paths,
                )
            )

        if not has_provider_config:
            findings.append(
                AnalysisFinding(
                    id="terraform_provider_missing",
                    title="Provider configuration not detected",
                    description="No Terraform provider block was found in scanned Terraform files.",
                    severity="medium",
                    evidence=terraform_file_paths,
                )
            )

        if not has_variables:
            findings.append(
                AnalysisFinding(
                    id="terraform_variables_missing",
                    title="Variables not detected",
                    description="No Terraform variable blocks were found in scanned Terraform files.",
                    severity="low",
                    evidence=terraform_file_paths,
                )
            )

        if not has_outputs:
            findings.append(
                AnalysisFinding(
                    id="terraform_outputs_missing",
                    title="Outputs not detected",
                    description="No Terraform output blocks were found in scanned Terraform files.",
                    severity="low",
                    evidence=terraform_file_paths,
                )
            )

        if module_files:
            findings.append(
                AnalysisFinding(
                    id="terraform_modules_detected",
                    title="Modules detected",
                    description="Terraform module blocks were found in scanned Terraform files.",
                    severity="info",
                    evidence=module_files,
                )
            )

        return findings
