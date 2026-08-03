import logging
import os
import stat as stat_module
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from app.core.domain.companion_assets import is_saver_chrome
from app.core.domain.folder_access import FolderPermissionError, is_permission_error
from app.core.domain.gitignore_matcher import GITIGNORE_FILENAME, GitignoreMatcher
from app.core.domain.project_scan import ProjectFile, ProjectFileList
from app.core.domain.source_files import (
    CONFIG_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SOURCE_CODE_EXTENSIONS,
    XML_CONFIG_EXTENSIONS,
    is_build_output,
    is_env_template,
    is_lockfile,
    is_os_clutter,
    is_secret_env_file,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
MAX_WRITTEN_FILE_SIZE_BYTES = 1024 * 1024
# Documents are allowed to be much larger than source files: a 40-page PDF or a
# Word runbook with images easily passes 2 MB while holding only a few pages of
# text. The extractor enforces its own ceiling (MAX_DOCUMENT_BYTES), so the scan
# just has to stop dropping them on the floor first.
DOCUMENT_SUFFIXES = {
    ".docx",
    ".xlsx",
    ".pptx",
    ".pdf",
    ".html",
    ".htm",
    ".csv",
    ".tsv",
    ".ipynb",
    ".drawio",
}
MAX_DOCUMENT_FILE_SIZE_BYTES = 20 * 1024 * 1024
SKIPPED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
}


class LocalFileSystem:
    def list_files(
        self,
        root_path: str,
        respect_gitignore: bool = True,
        progress: Callable[[int], None] | None = None,
    ) -> list[ProjectFile]:
        root = Path(root_path).resolve()
        walk_started = perf_counter()
        candidates = self._collect_candidates(
            root, respect_gitignore=respect_gitignore, progress=progress
        )
        walk_ms = (perf_counter() - walk_started) * 1000
        chart_roots = {
            relative_path.parent.as_posix()
            for relative_path, _, _, _ in candidates
            if relative_path.name == "Chart.yaml"
        }

        project_files: list[ProjectFile] = []
        skipped_files = 0
        total_size_bytes = 0

        classify_started = perf_counter()
        for relative_path, full_path, size_bytes, modified_at in candidates:
            limit = (
                MAX_DOCUMENT_FILE_SIZE_BYTES
                if relative_path.suffix.lower() in DOCUMENT_SUFFIXES
                else MAX_FILE_SIZE_BYTES
            )
            if size_bytes > limit:
                skipped_files += 1
                continue

            detected_type = self._detect_file_type(relative_path, full_path, chart_roots)
            project_files.append(
                ProjectFile(
                    path=relative_path.as_posix(),
                    extension=self._extension(relative_path),
                    size_bytes=size_bytes,
                    detected_type=detected_type,
                    modified_at=modified_at,
                )
            )
            total_size_bytes += size_bytes
        classify_ms = (perf_counter() - classify_started) * 1000

        # This is the "Enumerating files…" window the user sees before per-file
        # progress starts. Log the two sub-phases and the number of paths the walk
        # actually visited, so a slow scan on a tiny project can be told apart from
        # a walk dragging through a large sibling tree (visited ≫ kept). One line.
        logger.info(
            "scan.list_files walk=%.0fms classify=%.0fms visited=%d kept=%d root=%s",
            walk_ms,
            classify_ms,
            len(candidates),
            len(project_files),
            root,
        )

        return ProjectFileList(
            files=project_files,
            total_files=len(project_files) + skipped_files,
            skipped_files=skipped_files,
            total_size_bytes=total_size_bytes,
        )

    def path_exists(self, path: str) -> bool:
        return Path(path).exists()

    def is_directory(self, path: str) -> bool:
        return Path(path).is_dir()

    def read_text_file(self, root_path: str, relative_path: str) -> str:
        root = Path(root_path).resolve()
        target_path = (root / relative_path).resolve()

        try:
            target_path.relative_to(root)
        except ValueError:
            return ""

        if not target_path.is_file():
            return ""

        try:
            if target_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                return ""
            return target_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def write_text_file(
        self,
        root_path: str,
        relative_path: str,
        content: str,
        overwrite: bool = False,
    ) -> bool:
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise ValueError("Workspace project path does not exist or is not a directory")
        target_path = (root / relative_path).resolve()

        try:
            target_path.relative_to(root)
        except ValueError as exc:
            raise ValueError("Target path must stay inside the workspace") from exc

        if len(content.encode("utf-8")) > MAX_WRITTEN_FILE_SIZE_BYTES:
            raise ValueError("File content exceeds the 1 MB safety limit")

        replaced_existing = target_path.exists()
        if replaced_existing and not target_path.is_file():
            raise ValueError("Target path is not a file")
        if replaced_existing and not overwrite:
            raise FileExistsError("File already exists; enable overwrite after reviewing it")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return replaced_existing

    def _collect_candidates(
        self,
        root: Path,
        *,
        respect_gitignore: bool = True,
        progress: Callable[[int], None] | None = None,
    ) -> list[tuple[Path, Path, int, float | None]]:
        candidates: list[tuple[Path, Path, int, float | None]] = []

        def _on_walk_error(error: OSError) -> None:
            """os.walk swallows scandir errors by default, which is how a folder we are
            not allowed to read produced a *successful* scan with a silently smaller
            file set. Refuse to be quietly wrong.

            The root being unreadable is fatal — there is no project to scan, and the
            person needs to be told to grant access. A single unreadable directory
            deeper in the tree is not: we skip it and count it, the way we already skip
            an unreadable file."""
            if not is_permission_error(error):
                return
            if Path(error.filename or "").resolve() == root:
                raise FolderPermissionError(str(root))
            logger.info("scan.skip_unreadable_dir path=%s", error.filename)

        # Prune directories DURING the walk, not after, on two fronts:
        #   1. The hardcoded SKIPPED_DIRECTORIES (.git / node_modules / .venv / …).
        #   2. Anything the project's own .gitignore ignores — built incrementally as
        #      os.walk descends (top-down), matching git's per-directory semantics.
        # This is what makes a scan fast on a real repo: the scan filter already drops
        # every gitignored file unconditionally, so never descending into an ignored
        # tree yields the identical kept set while skipping the stat + classify + match
        # of (often the vast majority of) files. (``followlinks`` stays False so a
        # symlinked dir can't loop us.)
        gitignore_sources: dict[str, str] = {}
        matcher = GitignoreMatcher.empty()
        for dirpath, dirnames, filenames in os.walk(str(root), onerror=_on_walk_error):
            current_dir = Path(dirpath)
            rel_dir = "" if current_dir == root else current_dir.relative_to(root).as_posix()

            # Load this directory's .gitignore before deciding which children to
            # descend into, so its rules apply to its own subtree.
            if respect_gitignore and GITIGNORE_FILENAME in filenames:
                content = self._read_gitignore(current_dir / GITIGNORE_FILENAME)
                if content:
                    rel_gitignore = (
                        GITIGNORE_FILENAME if not rel_dir else f"{rel_dir}/{GITIGNORE_FILENAME}"
                    )
                    gitignore_sources[rel_gitignore] = content
                    matcher = GitignoreMatcher.from_sources(gitignore_sources)

            def _keep_dir(name: str) -> bool:
                if name in SKIPPED_DIRECTORIES:
                    return False
                if respect_gitignore and matcher.active:
                    child_rel = name if not rel_dir else f"{rel_dir}/{name}"
                    # Trailing slash so a directory-only rule ("build/") matches.
                    if matcher.is_ignored(f"{child_rel}/"):
                        return False
                return True

            dirnames[:] = [d for d in dirnames if _keep_dir(d)]
            for name in filenames:
                full_path = current_dir / name
                try:
                    stat_result = full_path.stat()
                except OSError:
                    continue
                # Regular files only (skip fifos/sockets; a symlink to a file
                # resolves to regular via stat, matching the old is_file() check).
                if not stat_module.S_ISREG(stat_result.st_mode):
                    continue

                size_bytes = stat_result.st_size
                try:
                    modified_at: float | None = stat_result.st_mtime
                except (OSError, AttributeError):
                    modified_at = None

                candidates.append((full_path.relative_to(root), full_path, size_bytes, modified_at))

            # A heartbeat, so a slow-but-healthy walk keeps ticking and only a *stuck*
            # one looks stuck. Without it the UI cannot tell "large repository" from
            # "blocked on a permission dialog" — and that is the whole difference
            # between waiting and being lost.
            if progress is not None:
                progress(len(candidates))

        return candidates

    @staticmethod
    def _read_gitignore(path: Path) -> str:
        """Read a ``.gitignore`` file for walk-time pruning; empty string on any
        error so a single unreadable file never breaks the scan."""
        try:
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                return ""
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _detect_file_type(
        self,
        relative_path: Path,
        full_path: Path,
        chart_roots: set[str],
    ) -> str:
        name = relative_path.name
        name_lower = name.lower()
        suffix = relative_path.suffix.lower()
        relative_posix = relative_path.as_posix()
        relative_lower = relative_posix.lower()

        # Machine-written or secret files first, before any format rule can claim
        # them: package-lock.json is JSON, pnpm-lock.yaml is YAML, and a minified
        # bundle is JavaScript. Left as "unknown" so they never reach the index — a
        # lockfile is tens of thousands of lines nobody reads, a bundle embeds to
        # noise, and a real .env holds credentials.
        if (
            is_lockfile(name)
            or is_secret_env_file(name)
            or is_build_output(relative_posix)
            or is_os_clutter(name)
        ):
            return "unknown"

        # The stylesheets, scripts and fonts a *saver* dropped into a document's
        # companion folder ("Page_files/style.css"). They describe how the page
        # looked, never what it said, and indexing them puts Confluence's CSS into
        # the answers. Only inside a companion folder — a .css in someone's own
        # project is theirs to keep.
        if is_saver_chrome(relative_posix):
            return "unknown"

        if relative_posix == ".gitlab-ci.yml" or relative_posix == ".gitlab-ci.yaml":
            return "gitlab_ci"
        if relative_lower.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}:
            return "github_actions"
        if suffix in {".tf", ".tfvars"}:
            return "terraform"
        if name_lower == "terragrunt.hcl" or (
            suffix == ".hcl" and self._looks_like_terragrunt_file(full_path)
        ):
            return "terragrunt"
        if suffix == ".py":
            return "python"
        if name_lower == "dockerfile" or name_lower.endswith(".dockerfile"):
            return "docker"
        if name == "Chart.yaml":
            return "helm"
        if suffix in {".yml", ".yaml"} and self._looks_like_kubernetes_manifest(full_path):
            return "kubernetes"
        if self._is_helm_template(relative_path, chart_roots):
            return "helm"
        if suffix == ".md":
            return "markdown"
        if suffix in {".yml", ".yaml"}:
            return "yaml"
        if suffix == ".json":
            return "json"
        if suffix == ".sh":
            return "shell"

        # Everything a real repository is actually made of. Without these a
        # TypeScript project scanned as "unknown" from top to bottom.
        if suffix == ".sql":
            return "sql"
        if suffix in SOURCE_CODE_EXTENSIONS:
            return "source_code"
        if suffix in CONFIG_EXTENSIONS or is_env_template(name):
            return "config"
        if suffix in XML_CONFIG_EXTENSIONS:
            return "xml_config"
        if name_lower in {"makefile", "gnumakefile"} or suffix == ".mk":
            return "makefile"
        if suffix in {".csv", ".tsv"}:
            return "tabular_data"
        if suffix == ".ipynb":
            return "notebook"
        # Office documents and pages. These are binary/markup containers, so they
        # are indexed through a DocumentTextExtractor rather than read as UTF-8.
        # A Confluence space export lands here as .html; runbooks as .docx.
        if suffix == ".docx":
            return "word_document"
        if suffix == ".xlsx":
            return "excel_workbook"
        if suffix == ".pptx":
            return "presentation"
        if suffix == ".pdf":
            return "pdf_document"
        # A diagram is XML, and every box on it carries its label. ".drawio.xml" is
        # the same file under the name draw.io's desktop app gives it.
        if suffix == ".drawio" or name_lower.endswith(".drawio.xml"):
            return "diagram"
        # Images: detected so they are *known* (an attachment of a page is often the
        # answer to "where is the architecture diagram?"), never indexed — we cannot
        # read a picture without OCR, and pretending otherwise would be a lie.
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in {".html", ".htm"}:
            return "html"
        if suffix in {".txt", ".rst", ".adoc"}:
            return "plain_text"

        return "unknown"

    @staticmethod
    def _extension(path: Path) -> str | None:
        return path.suffix.lower() or None

    @staticmethod
    def _is_helm_template(relative_path: Path, chart_roots: set[str]) -> bool:
        parts = relative_path.parts
        if "templates" not in parts:
            return False

        template_index = parts.index("templates")
        chart_root = Path(*parts[:template_index]).as_posix() if template_index else "."
        return chart_root in chart_roots

    @staticmethod
    def _looks_like_kubernetes_manifest(path: Path) -> bool:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False

        return "apiVersion:" in content and "kind:" in content

    @staticmethod
    def _looks_like_terragrunt_file(path: Path) -> bool:
        try:
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                return False
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False

        # Distinctive Terragrunt blocks and functions. Named includes
        # (`include "root" {`) and Terragrunt-only functions are the reliable
        # tells — plain `terraform {` also appears in vanilla HCL, so we lead
        # with the unambiguous signals.
        terragrunt_signals = [
            "include {",
            'include "',
            'dependency "',
            "dependencies {",
            'generate "',
            "remote_state {",
            "find_in_parent_folders(",
            "read_terragrunt_config(",
            "path_relative_to_include(",
            "get_terragrunt_dir(",
            "get_parent_terragrunt_dir(",
            "inputs =",
            "terraform {",
        ]
        return any(signal in content for signal in terragrunt_signals)
