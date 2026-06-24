"""Deterministic Python application analyzer.

Reads the files the scanner tagged ``python`` and, using only the standard
library's ``ast`` (parse, never execute), derives:

* the web/app **framework(s)** in use (FastAPI / Flask / Django / Celery),
* likely **entrypoints** (main.py, manage.py, ``if __name__ == "__main__"`` …),
* the project's top-level **modules** and the import edges *between* them
  (the internal architecture), and
* **notable third-party dependencies** from the dependency manifests, mapped to
  friendly names (a curated set, so the list stays meaningful rather than noisy).

No code is executed and nothing is written. Parsing is bounded so very large
repositories stay responsive.
"""

import ast
import posixpath
import re
from dataclasses import dataclass

from app.core.domain.analysis import (
    AnalysisFinding,
    PythonAnalysisResult,
    PythonModule,
)
from app.core.ports.file_system import FileSystemPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

_MAX_FILES = 1200

# import-name → framework label
_FRAMEWORK_IMPORTS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "celery": "Celery",
    "aiohttp": "aiohttp",
    "starlette": "Starlette",
    "tornado": "Tornado",
}

_ENTRYPOINT_BASENAMES = {"main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "__main__.py"}

# normalised distribution name → friendly label (curated; unknown deps dropped)
_NOTABLE_DEPS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "celery": "Celery",
    "starlette": "Starlette",
    "uvicorn": "Uvicorn",
    "gunicorn": "Gunicorn",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "pydantic": "Pydantic",
    "psycopg2": "PostgreSQL driver",
    "psycopg2-binary": "PostgreSQL driver",
    "psycopg": "PostgreSQL driver",
    "asyncpg": "PostgreSQL (async)",
    "pymysql": "MySQL driver",
    "mysqlclient": "MySQL driver",
    "redis": "Redis",
    "pymongo": "MongoDB driver",
    "boto3": "AWS SDK",
    "requests": "requests",
    "httpx": "httpx",
    "aiohttp": "aiohttp",
    "pandas": "pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "pika": "RabbitMQ client",
    "kafka-python": "Kafka client",
    "confluent-kafka": "Kafka client",
    "grpcio": "gRPC",
    "pytest": "pytest",
}

_REQUIREMENTS_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_DEP_MANIFESTS = {"requirements.txt", "pyproject.toml", "setup.cfg", "setup.py", "Pipfile"}


def _posix(path: str) -> str:
    return path.replace("\\", "/")


def _module_of(path: str) -> str:
    parts = [p for p in _posix(path).split("/") if p]
    if parts and parts[0] in {"src", "lib"} and len(parts) > 1:
        parts = parts[1:]
    if len(parts) <= 1:
        return "(root)"
    return parts[0]


@dataclass(frozen=True)
class AnalyzePythonInput:
    workspace_id: str


class PythonAnalysisWorkspaceNotFoundError(ValueError):
    pass


class PythonAnalysisScanRequiredError(ValueError):
    pass


class AnalyzePythonUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        file_system: FileSystemPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.file_system = file_system

    def execute(self, request: AnalyzePythonInput) -> PythonAnalysisResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise PythonAnalysisWorkspaceNotFoundError("Workspace not found")

        latest_scan = self.project_scan_repository.get_latest_scan(request.workspace_id)
        if latest_scan is None:
            raise PythonAnalysisScanRequiredError("Project scan required before analysis")

        all_paths = [_posix(f.path) for f in latest_scan.files]
        py_paths = sorted(p for p in all_paths if p.endswith(".py"))[:_MAX_FILES]

        package_names = {m for p in py_paths if (m := _module_of(p)) != "(root)"}
        imports_by_module: dict[str, set[str]] = {}
        module_path: dict[str, str] = {}
        frameworks: set[str] = set()
        entrypoints: list[str] = []
        has_tests = False

        for path in py_paths:
            module = _module_of(path)
            module_path.setdefault(module, path)
            base = posixpath.basename(path)
            if (
                "/tests/" in f"/{path}"
                or "/test/" in f"/{path}"
                or base.startswith("test_")
                or base == "conftest.py"
            ):
                has_tests = True

            content = self.file_system.read_text_file(
                root_path=workspace.project_path, relative_path=path
            )
            tops = self._top_level_imports(content)
            for top in tops:
                if top in _FRAMEWORK_IMPORTS:
                    frameworks.add(_FRAMEWORK_IMPORTS[top])
                if top in package_names and top != module:
                    imports_by_module.setdefault(module, set()).add(top)

            if self._is_entrypoint(base, content) and len(entrypoints) < 12:
                entrypoints.append(path)

        modules = [
            PythonModule(
                name=name,
                path=module_path.get(name, name),
                internal_imports=sorted(imports_by_module.get(name, set())),
            )
            for name in sorted(package_names)
        ]

        dependency_files = sorted(
            p for p in all_paths if self._is_dependency_manifest(posixpath.basename(p))
        )
        notable = self._notable_dependencies(workspace.project_path, dependency_files)
        frameworks |= {
            label for label in notable if label in {"FastAPI", "Flask", "Django", "Celery"}
        }

        findings: list[AnalysisFinding] = []
        if not dependency_files:
            findings.append(
                AnalysisFinding(
                    id="python_no_dependency_manifest",
                    title="No dependency manifest found",
                    description="No requirements.txt, pyproject.toml or similar was detected, so the project's dependencies are not pinned in one place.",
                    severity="low",
                    evidence=[],
                )
            )
        if py_paths and not has_tests:
            findings.append(
                AnalysisFinding(
                    id="python_no_tests",
                    title="No test files detected",
                    description="No tests/ directory or test_*.py files were found, so automated test coverage is unclear.",
                    severity="info",
                    evidence=[],
                )
            )

        return PythonAnalysisResult(
            workspace_id=workspace.id,
            project_path=workspace.project_path,
            python_files_count=len([p for p in all_paths if p.endswith(".py")]),
            frameworks=sorted(frameworks),
            entrypoints=entrypoints,
            modules=modules,
            notable_dependencies=notable,
            has_tests=has_tests,
            dependency_files=dependency_files,
            findings=findings,
        )

    @staticmethod
    def _top_level_imports(content: str) -> set[str]:
        try:
            tree = ast.parse(content)
        except (SyntaxError, ValueError):
            return set()
        tops: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    tops.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                # level > 0 is a relative (intra-package) import — not cross-module.
                if node.level == 0 and node.module:
                    tops.add(node.module.split(".")[0])
        return tops

    @staticmethod
    def _is_entrypoint(basename: str, content: str) -> bool:
        if basename in _ENTRYPOINT_BASENAMES:
            return True
        if re.search(r"__name__\s*==\s*['\"]__main__['\"]", content):
            return True
        if re.search(r"\b(FastAPI|Flask)\s*\(", content):
            return True
        return False

    @staticmethod
    def _is_dependency_manifest(basename: str) -> bool:
        if basename in _DEP_MANIFESTS:
            return True
        return bool(re.match(r"requirements.*\.txt$", basename))

    def _notable_dependencies(self, project_path: str, dependency_files: list[str]) -> list[str]:
        raw: set[str] = set()
        for path in dependency_files:
            base = posixpath.basename(path)
            content = self.file_system.read_text_file(root_path=project_path, relative_path=path)
            if base.endswith(".txt"):
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith(("#", "-")):
                        continue
                    match = _REQUIREMENTS_RE.match(stripped)
                    if match:
                        raw.add(match.group(1).lower())
            else:
                # pyproject.toml / setup.cfg / Pipfile: scan for known names rather
                # than fully parsing every dialect (TOML/INI). Each lookup is a
                # whole-word match, so we never partial-match a longer package.
                lowered = content.lower()
                for dep in _NOTABLE_DEPS:
                    if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(dep)}(?![A-Za-z0-9_-])", lowered):
                        raw.add(dep)

        labels: list[str] = []
        seen: set[str] = set()
        for dep in sorted(raw):
            label = _NOTABLE_DEPS.get(dep)
            if label and label not in seen:
                seen.add(label)
                labels.append(label)
        return labels[:14]
