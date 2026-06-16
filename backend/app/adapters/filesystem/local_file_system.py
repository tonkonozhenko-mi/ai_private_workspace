from pathlib import Path

from app.core.domain.project_scan import ProjectFile, ProjectFileList

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
MAX_WRITTEN_FILE_SIZE_BYTES = 1024 * 1024
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
    def list_files(self, root_path: str) -> list[ProjectFile]:
        root = Path(root_path).resolve()
        candidates = self._collect_candidates(root)
        chart_roots = {
            relative_path.parent.as_posix()
            for relative_path, _, _, _ in candidates
            if relative_path.name == "Chart.yaml"
        }

        project_files: list[ProjectFile] = []
        skipped_files = 0
        total_size_bytes = 0

        for relative_path, full_path, size_bytes, modified_at in candidates:
            if size_bytes > MAX_FILE_SIZE_BYTES:
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

    def _collect_candidates(self, root: Path) -> list[tuple[Path, Path, int, float | None]]:
        candidates: list[tuple[Path, Path, int, float | None]] = []

        for current_path in root.rglob("*"):
            if self._is_in_skipped_directory(current_path.relative_to(root)):
                continue
            if not current_path.is_file():
                continue

            try:
                stat_result = current_path.stat()
            except OSError:
                continue

            size_bytes = stat_result.st_size
            try:
                modified_at: float | None = stat_result.st_mtime
            except (OSError, AttributeError):
                modified_at = None

            candidates.append(
                (current_path.relative_to(root), current_path, size_bytes, modified_at)
            )

        return candidates

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

        return "unknown"

    @staticmethod
    def _extension(path: Path) -> str | None:
        return path.suffix.lower() or None

    @staticmethod
    def _is_in_skipped_directory(relative_path: Path) -> bool:
        return any(part in SKIPPED_DIRECTORIES for part in relative_path.parts[:-1])

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

        terragrunt_signals = [
            "terraform {",
            "include {",
            'dependency "',
            "inputs =",
            "remote_state {",
        ]
        return any(signal in content for signal in terragrunt_signals)
