"""Deterministic external-reference scanner.

Scans the project's text files for the external things it points at — URLs,
Terraform/Git module sources, AWS ARNs and S3 URIs — then de-duplicates, counts
and ranks them. Bounded so large repositories stay responsive. Read-only.
"""

import re
from collections import defaultdict
from dataclasses import dataclass

from app.core.domain.analysis import ReferenceAnalysisResult, ReferenceItem
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

_TEXT_TYPES = {
    "terraform",
    "terragrunt",
    "github_actions",
    "gitlab_ci",
    "python",
    "yaml",
    "json",
    "shell",
    "markdown",
    "helm",
    "kubernetes",
    "docker",
}

_MAX_FILES = 1000
_MAX_PER_KIND = 30

_URL_RE = re.compile(r"https?://[^\s\"'`<>)\]}]+")
_ARN_RE = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]*:[^\s\"'`<>)\]}]+")
_S3_RE = re.compile(r"s3://[a-z0-9.\-/_]+", re.IGNORECASE)
_SOURCE_RE = re.compile(r'source\s*=\s*"([^"]+)"')

# Boilerplate domains that are noise rather than real project dependencies.
# These are mostly documentation links pasted into comments by code generators
# (provider docs), not things the project actually depends on.
_NOISE_HOSTS = (
    "www.w3.org",
    "schema.org",
    "json-schema.org",
    "example.com",
    "example.org",
    "localhost",
    "127.0.0.1",
    "schemas.",
    "registry.terraform.io",
    "registry.opentofu.org",
    "docs.aws.amazon.com",
    "docs.microsoft.com",
    "learn.microsoft.com",
    "cloud.google.com/docs",
    "developer.hashicorp.com",
    "terraform.io/docs",
)


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:)\"'`")


def _is_noise(url: str) -> bool:
    return any(host in url for host in _NOISE_HOSTS)


def _is_template(value: str) -> bool:
    """Unresolved templates / placeholders are not real references."""
    lowered = value.lower()
    return "${" in value or ":tbd:" in lowered or lowered.endswith(":tbd") or "<" in value


def _looks_like_module_source(value: str) -> bool:
    if value.startswith((".", "/")):  # local path, not external
        return False
    return (
        value.startswith(("git::", "github.com/", "git@"))
        or "//" in value  # registry sub-module syntax
        or value.count("/") >= 2  # registry namespace/name/provider
    )


@dataclass(frozen=True)
class AnalyzeReferencesInput:
    workspace_id: str


class ReferencesAnalysisWorkspaceNotFoundError(ValueError):
    pass


class ReferencesAnalysisScanRequiredError(ValueError):
    pass


class AnalyzeReferencesUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzeReferencesInput) -> ReferenceAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise ReferencesAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise ReferencesAnalysisScanRequiredError("Project scan required before analysis")

        files = [f for f in latest_scan.files if f.detected_type in _TEXT_TYPES][:_MAX_FILES]

        # (kind, value) -> [count, first_source]
        seen: dict[tuple[str, str], list] = defaultdict(lambda: [0, None])

        def record(kind: str, value: str, source: str) -> None:
            entry = seen[(kind, value)]
            entry[0] += 1
            if entry[1] is None:
                entry[1] = source

        for project_file in files:
            content = self.file_system.read_text_file(
                root_path=workspace.project_path, relative_path=project_file.path
            )
            for raw in _URL_RE.findall(content):
                url = _clean_url(raw)
                if not _is_noise(url) and not _is_template(url):
                    record("url", url, project_file.path)
            for arn in _ARN_RE.findall(content):
                cleaned = arn.rstrip(".,;:)\"'`")
                if not _is_template(cleaned):
                    record("aws_arn", cleaned, project_file.path)
            for bucket in _S3_RE.findall(content):
                if not _is_template(bucket):
                    record("s3_bucket", bucket, project_file.path)
            for source in _SOURCE_RE.findall(content):
                if _looks_like_module_source(source) and not _is_template(source):
                    record("module_source", source, project_file.path)

        # Rank within each kind and cap, so the list stays meaningful.
        by_kind: dict[str, list[ReferenceItem]] = defaultdict(list)
        for (kind, value), (count, source) in seen.items():
            by_kind[kind].append(
                ReferenceItem(kind=kind, value=value, count=count, source_file=source or "")
            )
        references: list[ReferenceItem] = []
        for kind, items in by_kind.items():
            items.sort(key=lambda r: (-r.count, r.value))
            references.extend(items[:_MAX_PER_KIND])

        return ReferenceAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            references=references,
        )
