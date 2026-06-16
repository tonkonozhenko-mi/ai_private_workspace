import re
from dataclasses import dataclass

from app.core.domain.project_todos import ProjectTodo, ProjectTodos
from app.core.ports.file_system import FileSystemPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.scan_project import ScanProjectInput, ScanProjectUseCase

# Match a TODO-style marker as a whole word, optionally followed by ":" or "(owner)".
_MARKER_RE = re.compile(
    r"\b(TODO|FIXME|HACK|XXX|BUG)\b[\s:()\w]*?[:\-]?\s*(.*)$",
    re.IGNORECASE,
)
_MARKERS = ("TODO", "FIXME", "HACK", "XXX", "BUG")
# Only scan source-like text files; skip data/lock/docs noise that produces
# false positives or huge useless matches.
_SCANNABLE_EXTENSIONS = {
    "py",
    "ts",
    "tsx",
    "js",
    "jsx",
    "mjs",
    "cjs",
    "rs",
    "go",
    "java",
    "kt",
    "rb",
    "php",
    "c",
    "cc",
    "cpp",
    "h",
    "hpp",
    "cs",
    "swift",
    "scala",
    "vue",
    "svelte",
    "sh",
    "bash",
    "sql",
    "lua",
    "yaml",
    "yml",
    "toml",
}
_MAX_ITEMS = 60
_MAX_TEXT_LEN = 160


@dataclass(frozen=True)
class GetWorkspaceTodosInput:
    workspace_id: str
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()


class WorkspaceTodosNotFoundError(ValueError):
    pass


class GetWorkspaceTodosUseCase:
    """Deterministically collect TODO/FIXME-style markers from project files.

    Read-only: it walks the project with the same selection rules as scanning
    (so virtualenvs, ``node_modules`` and gitignored files are excluded) and
    greps file contents. Nothing is generated or persisted.
    """

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        file_system: FileSystemPort,
        scan_use_case: ScanProjectUseCase,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.file_system = file_system
        self.scan_use_case = scan_use_case

    def execute(self, request: GetWorkspaceTodosInput) -> ProjectTodos:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceTodosNotFoundError("Workspace not found")

        scan = self.scan_use_case.execute(
            ScanProjectInput(
                project_path=workspace.project_path,
                include_patterns=request.include_patterns,
                exclude_patterns=request.exclude_patterns,
                respect_gitignore=True,
            )
        )

        items: list[ProjectTodo] = []
        total = 0
        for project_file in scan.files:
            extension = (project_file.extension or "").lower()
            if extension not in _SCANNABLE_EXTENSIONS:
                continue
            content = self._safe_read(workspace.project_path, project_file.path)
            if not content:
                continue
            for line_number, line in enumerate(content.splitlines(), start=1):
                parsed = _parse_marker(line)
                if parsed is None:
                    continue
                marker, text = parsed
                total += 1
                if len(items) < _MAX_ITEMS:
                    items.append(
                        ProjectTodo(
                            file=project_file.path,
                            line=line_number,
                            marker=marker,
                            text=text,
                        )
                    )

        return ProjectTodos(
            total=total,
            truncated=total > len(items),
            items=items,
        )

    def _safe_read(self, root_path: str, relative_path: str) -> str:
        try:
            return self.file_system.read_text_file(root_path, relative_path)
        except Exception:
            return ""


_COMMENT_OPENERS = ("#", "//", "/*", "*", "<!--", "--", ";", "%", '"""', "'''")


def _parse_marker(line: str) -> tuple[str, str] | None:
    # Fast reject before the regex.
    upper = line.upper()
    if not any(marker in upper for marker in _MARKERS):
        return None
    match = _MARKER_RE.search(line)
    if match is None:
        return None

    marker = match.group(1).upper()
    before = line[: match.start(1)].rstrip()
    after = line[match.end(1) :]
    # Only treat it as a real marker when it sits in a code comment or is written
    # as a tag followed by a colon or an owner in parentheses. This avoids false
    # positives like the marker word appearing inside prose or a string literal.
    in_comment = before.endswith(_COMMENT_OPENERS)
    is_tag = after[:1] in {":", "("}
    if not (in_comment or is_tag):
        return None

    text = match.group(2).strip()
    # Strip a leading owner tag like "(maks)" and separators.
    text = re.sub(r"^\(.*?\)\s*", "", text)
    text = text.lstrip(":-) ").strip()
    # Drop trailing comment-close tokens like "*/" or "-->".
    text = re.sub(r"\s*(\*/|-->|#\})\s*$", "", text).strip()
    # Ignore matches whose remaining text has no letters (e.g. stray quotes),
    # which are almost always false positives rather than real notes.
    if not any(char.isalpha() for char in text):
        return None
    return marker, text[:_MAX_TEXT_LEN]
