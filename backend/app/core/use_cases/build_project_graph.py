"""Build the Project Intelligence graph for a workspace.

Composes the existing deterministic analyzers (Terraform / Terragrunt / GitLab CI
/ GitHub Actions) into one role-neutral ``ProjectGraph`` and persists it as a
snapshot. Runs only on explicit request; never on startup. Mirrors the analyzer
orchestration in ``get_analysis_summary`` so behaviour stays consistent.
"""

import hashlib
from dataclasses import dataclass

from app.core.domain.project_graph import ProjectSnapshotMeta
from app.core.domain.project_graph_builder import build_project_graph
from app.core.domain.source_files import SOURCE_CODE
from app.core.ports.file_system import FileSystemPort
from app.core.ports.git_history import GitHistoryPort
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
from app.core.use_cases.analyze_role_facts import (
    AnalyzeRoleFactsInput,
    AnalyzeRoleFactsUseCase,
)
from app.core.use_cases.analyze_terraform import AnalyzeTerraformInput, AnalyzeTerraformUseCase
from app.core.use_cases.analyze_terragrunt import (
    AnalyzeTerragruntInput,
    AnalyzeTerragruntUseCase,
)


@dataclass(frozen=True)
class BuildProjectGraphInput:
    workspace_id: str
    # When False, the build is skipped if the files (by content hash) and app
    # version are unchanged since the last snapshot — the graph would be identical,
    # so re-running the analyzers is wasted work. Set True to force a rebuild.
    force: bool = False


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
        git_history: GitHistoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        self.project_graph_repository = project_graph_repository
        # Optional: ownership ("who alone knows this file") is a git fact. Without a
        # repository there is simply no ownership section — not a broken map.
        self.git_history = git_history

    def execute(self, request: BuildProjectGraphInput) -> ProjectSnapshotMeta:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise BuildProjectGraphWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise BuildProjectGraphScanRequiredError("Project scan required before analysis")

        # Skip the (expensive) analyzer pass when nothing that affects the graph
        # changed: same files (by content hash) and same app version. The result
        # would be byte-for-byte identical, so reuse the last snapshot.
        signature = self._scan_signature(latest_scan)
        if not request.force:
            previous = self.project_graph_repository.get_latest_snapshot_meta(request.workspace_id)
            if previous is not None and previous.scan_signature == signature:
                return previous

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

        # The facts every role other than DevOps was missing. Each analyzer degrades
        # to None on its own — a project with no SQL, no tests or no HTTP routes must
        # still get a map of everything else.
        role_facts = AnalyzeRoleFactsUseCase(
            self.workspace_repository,
            self.project_scan_repository,
            self.file_system,
            git_history=self.git_history,
        )
        facts_request = AnalyzeRoleFactsInput(workspace_id=ws_id)

        def _facts(name: str, run):
            try:
                return run()
            except Exception:  # noqa: BLE001 - one analyzer must not lose the whole map
                skipped.append(name)
                return None

        # CI job names let the test analyzer answer "does anything actually run these
        # in the pipeline" from the pipeline's own jobs rather than from a guess.
        ci_job_names: list[str] = []
        if github_actions is not None:
            for workflow in github_actions.workflows:
                ci_job_names += workflow.job_names
        if gitlab_ci is not None:
            ci_job_names += [job.name for job in gitlab_ci.jobs]

        sql_schema = _facts("sql", lambda: role_facts.sql_schema(facts_request))
        tests = _facts("tests", lambda: role_facts.tests(facts_request, ci_job_names=ci_job_names))
        javascript = _facts("javascript", lambda: role_facts.javascript(facts_request))
        api_surface = _facts("api", lambda: role_facts.api_surface(facts_request))
        ownership = _facts("ownership", lambda: role_facts.ownership(facts_request))
        # A folder of documentation is not a broken repository — it is a different kind
        # of project, with facts of its own. Skipped silently when there are no pages.
        knowledge_base = _facts("documentation", lambda: role_facts.knowledge_base(facts_request))

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
            sql_schema=sql_schema,
            knowledge_base=knowledge_base,
            tests=tests,
            javascript=javascript,
            api_surface=api_surface,
            ownership=ownership,
            scan_paths=[project_file.path for project_file in latest_scan.files],
            # Lets the graph name the language a non-Python codebase is written in;
            # without it a TypeScript repo has no application entity at all.
            source_paths=[
                project_file.path
                for project_file in latest_scan.files
                if project_file.detected_type == SOURCE_CODE
            ],
            analyzers_skipped=skipped,
        )
        return self.project_graph_repository.save_graph(graph, scan_signature=signature)

    @staticmethod
    def _scan_signature(latest_scan) -> str:
        """Content + version fingerprint of the scan. Changes when any file's
        path/size/mtime changes, or the app version changes (so analyzer
        improvements take effect on the next build even if files didn't change)."""
        try:
            from app.config.settings import APP_VERSION

            version = APP_VERSION
        except Exception:  # noqa: BLE001 - version is best-effort; only busts cache
            version = ""
        parts = sorted(
            f"{f.path}:{getattr(f, 'size_bytes', '')}:{getattr(f, 'modified_at', '')}"
            for f in latest_scan.files
        )
        digest = hashlib.sha256(
            ("v=" + version + "|" + "|".join(parts)).encode("utf-8")
        ).hexdigest()
        return f"sha256:{digest[:16]}:files:{len(latest_scan.files)}"
