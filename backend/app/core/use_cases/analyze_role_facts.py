"""Read the files, hand back the facts each role came for.

Four analyzers in one module because they share every line of their plumbing —
find the workspace, take the latest scan, read a bounded set of files — and differ
only in which pure domain function they then call. Splitting them into four
identical classes would be ceremony, not clarity.

Each one degrades the same way: no files of its kind, no facts, no complaint. The
graph builder treats a missing analyzer as a missing analyzer, never as an empty
project.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.domain.api_surface import ApiSurface, build_api_surface
from app.core.domain.js_modules import JsFacts, build_js_facts
from app.core.domain.knowledge_base import KnowledgeBase, PageSource, build_knowledge_base
from app.core.domain.ownership import OwnershipFacts, build_ownership_facts
from app.core.domain.sql_schema import SqlSchema, build_sql_schema
from app.core.domain.test_suites import TestFacts, build_test_facts
from app.core.ports.file_system import FileSystemPort
from app.core.ports.git_history import GitHistoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

# One project should never make us read half a gigabyte to draw a map. These caps are
# generous for a real repository and hard for a pathological one.
_MAX_SQL_FILES = 400
_MAX_CODE_FILES = 1500
_MAX_OWNERSHIP_FILES = 40
# Reading every page of a 5,000-page wiki to count its links would cost more than the
# insight is worth; the first thousand pages describe the place.
_MAX_PAGES = 1000
# What counts as a *page* — something a person reads and links to. A spreadsheet in a
# page's folder is an attachment, not a page: putting "costs.xlsx" in a table of
# contents would be a category error.
_PAGE_TYPES = {"html", "markdown", "plain_text"}


@dataclass(frozen=True)
class AnalyzeRoleFactsInput:
    workspace_id: str


class RoleFactsWorkspaceNotFoundError(ValueError):
    pass


class RoleFactsScanRequiredError(ValueError):
    pass


class AnalyzeRoleFactsUseCase:
    """Facts for the DBA, the tester, the developer, the analyst and the manager."""

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
        git_history: GitHistoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system
        # Optional: ownership needs git. Without a repository we simply have no
        # ownership facts — which is the truth, not a failure.
        self.git_history = git_history

    # -- shared plumbing ----------------------------------------------------
    def _context(self, workspace_id: str):
        workspace = self.workspace_repository.get(workspace_id)
        if workspace is None:
            raise RoleFactsWorkspaceNotFoundError("Workspace not found")
        latest_scan = self.project_scan_repository.get_latest_scan(workspace_id)
        if latest_scan is None:
            raise RoleFactsScanRequiredError("Project scan required before analysis")
        return workspace, latest_scan

    def _read(self, project_path: str, paths: list[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        for path in paths:
            text = self.file_system.read_text_file(root_path=project_path, relative_path=path)
            if text:
                contents[path] = text
        return contents

    # -- the four analyzers -------------------------------------------------
    def sql_schema(self, request: AnalyzeRoleFactsInput) -> SqlSchema:
        workspace, scan = self._context(request.workspace_id)
        paths = sorted(f.path for f in scan.files if f.detected_type == "sql")[:_MAX_SQL_FILES]
        contents = self._read(workspace.project_path, paths)
        return build_sql_schema([(path, contents[path]) for path in sorted(contents)])

    def tests(
        self, request: AnalyzeRoleFactsInput, ci_job_names: list[str] | None = None
    ) -> TestFacts:
        workspace, scan = self._context(request.workspace_id)
        # Tests can be written in any language, and the commands that run them live in
        # the Makefile and package.json — so this analyzer reads code AND config.
        code_types = {"python", "source_code", "shell", "makefile", "json", "yaml"}
        paths = sorted(f.path for f in scan.files if f.detected_type in code_types)[
            :_MAX_CODE_FILES
        ]
        contents = self._read(workspace.project_path, paths)
        source_paths = [f.path for f in scan.files if f.detected_type in {"python", "source_code"}]
        return build_test_facts(contents, source_paths, ci_job_names=ci_job_names)

    def javascript(self, request: AnalyzeRoleFactsInput) -> JsFacts:
        workspace, scan = self._context(request.workspace_id)
        paths = sorted(
            f.path
            for f in scan.files
            if f.detected_type == "source_code" or f.path.endswith("package.json")
        )[:_MAX_CODE_FILES]
        contents = self._read(workspace.project_path, paths)
        return build_js_facts(contents)

    def api_surface(self, request: AnalyzeRoleFactsInput) -> ApiSurface:
        workspace, scan = self._context(request.workspace_id)
        paths = sorted(f.path for f in scan.files if f.detected_type in {"python", "source_code"})[
            :_MAX_CODE_FILES
        ]
        contents = self._read(workspace.project_path, paths)
        return build_api_surface(contents)

    def ownership(self, request: AnalyzeRoleFactsInput) -> OwnershipFacts:
        """Who alone knows which busy file. Only the hotspots are inspected: asking git
        for the authors of every file in a large repository would cost minutes, and the
        files nobody changes are not where the risk is."""
        if self.git_history is None:
            return OwnershipFacts()
        workspace, _ = self._context(request.workspace_id)
        insights = self.git_history.read_insights(workspace.project_path)
        if not insights.is_repo:
            return OwnershipFacts()

        activity: list[tuple[str, int, list[tuple[str, int]]]] = []
        for hotspot in insights.hotspots[:_MAX_OWNERSHIP_FILES]:
            file_activity = self.git_history.file_activity(workspace.project_path, hotspot.path)
            if file_activity is None or not file_activity.top_authors:
                continue
            activity.append(
                (
                    hotspot.path,
                    file_activity.total_commits,
                    [(author.name, author.commits) for author in file_activity.top_authors],
                )
            )
        return build_ownership_facts(activity)

    def knowledge_base(self, request: AnalyzeRoleFactsInput) -> KnowledgeBase:
        """What a folder of documentation knows about itself: its pages, the areas its
        own titles announce, the links between them, its decisions, and which pages are
        old enough to be wrong while others still rely on them.

        Reads the raw markup, not the extracted text: the links live in the markup, and
        throwing markup away is precisely the extractor's job.
        """
        workspace, scan = self._context(request.workspace_id)
        pages = [f for f in scan.files if f.detected_type in _PAGE_TYPES][:_MAX_PAGES]
        contents = self._read(workspace.project_path, [f.path for f in pages])
        sources = [
            PageSource(
                path=page.path,
                text=contents.get(page.path, ""),
                modified_at=_as_datetime(page.modified_at),
            )
            for page in pages
        ]
        return build_knowledge_base(sources, all_paths=[f.path for f in scan.files])


def _as_datetime(modified_at):  # noqa: ANN001, ANN201 - a scan timestamp, or nothing
    """The scan records mtime as a POSIX timestamp; freshness needs a real date."""
    if modified_at is None:
        return None
    if isinstance(modified_at, datetime):
        return modified_at if modified_at.tzinfo else modified_at.replace(tzinfo=UTC)
    try:
        return datetime.fromtimestamp(float(modified_at), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None
