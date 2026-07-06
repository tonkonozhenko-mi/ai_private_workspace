"""Project Intelligence M4: Python analyzer + builder composition."""

from types import SimpleNamespace

from app.adapters.memory.in_memory_project_graph_repository import (
    InMemoryProjectGraphRepository,
)
from app.core.domain.project_graph import EntityType, RelationType
from app.core.use_cases.analyze_python import AnalyzePythonInput, AnalyzePythonUseCase
from app.core.use_cases.build_project_graph import (
    BuildProjectGraphInput,
    BuildProjectGraphUseCase,
)

_WS = SimpleNamespace(id="w1", project_path="/p")

_FILES = {
    "api/main.py": (
        "from fastapi import FastAPI\n"
        "from db import session\n"
        "from core import settings\n"
        "app = FastAPI()\n"
        "if __name__ == '__main__':\n    app.run()\n"
    ),
    "api/routes.py": "from db import models\n",
    "db/__init__.py": "",
    "db/session.py": "import sqlalchemy\n",
    "db/models.py": "from core import base\n",
    "core/__init__.py": "",
    "core/settings.py": "import os\n",
    "core/base.py": "",
    "tests/test_main.py": "def test_x():\n    assert True\n",
    "requirements.txt": "fastapi==0.110\nsqlalchemy>=2.0\nredis\n# a comment\nrequests\n",
}


def _scan():
    files = [SimpleNamespace(path=p, detected_type="python") for p in _FILES if p.endswith(".py")]
    files.append(SimpleNamespace(path="requirements.txt", detected_type="unknown"))
    return SimpleNamespace(files=files)


class _WSRepo:
    def get(self, workspace_id):
        return _WS if workspace_id == "w1" else None


class _ScanRepo:
    def get_latest_scan(self, workspace_id):
        return _scan()


class _FS:
    def read_text_file(self, root_path, relative_path):
        return _FILES.get(relative_path, "")


def test_python_analyzer_detects_framework_modules_imports():
    result = AnalyzePythonUseCase(_WSRepo(), _ScanRepo(), _FS()).execute(
        AnalyzePythonInput(workspace_id="w1")
    )
    assert "FastAPI" in result.frameworks
    assert result.has_tests is True
    assert "api/main.py" in result.entrypoints
    module_names = {m.name for m in result.modules}
    assert {"api", "db", "core"} <= module_names
    # api imports db and core (cross-module edges).
    api = next(m for m in result.modules if m.name == "api")
    assert "db" in api.internal_imports and "core" in api.internal_imports
    # db imports core.
    db = next(m for m in result.modules if m.name == "db")
    assert "core" in db.internal_imports
    assert "SQLAlchemy" in result.notable_dependencies
    assert "Redis" in result.notable_dependencies


def test_build_graph_includes_application_modules_dependencies():
    repo = InMemoryProjectGraphRepository()
    meta = BuildProjectGraphUseCase(_WSRepo(), _ScanRepo(), _FS(), repo).execute(
        BuildProjectGraphInput(workspace_id="w1")
    )
    assert "python" in meta.analyzers_run

    graph = repo.get_latest_graph("w1")
    apps = graph.entities_of_type(EntityType.APPLICATION)
    assert len(apps) == 1
    assert "FastAPI" in apps[0].metadata.get("frameworks", "")
    modules = {m.name for m in graph.entities_of_type(EntityType.MODULE)}
    assert {"api", "db", "core"} <= modules
    deps = {d.name for d in graph.entities_of_type(EntityType.DEPENDENCY)}
    assert "SQLAlchemy" in deps
    # module -> module DEPENDS_ON edges exist.
    depends = [
        r
        for r in graph.relations_of_type(RelationType.DEPENDS_ON)
        if r.source_entity_id.startswith("module:")
    ]
    assert depends, "expected internal module dependency edges"


def test_presenter_surfaces_python_in_chips_and_description():
    from app.core.domain.project_intelligence_view import present_project_intelligence
    from app.core.domain.role_lens import role_lens_for

    repo = InMemoryProjectGraphRepository()
    BuildProjectGraphUseCase(_WSRepo(), _ScanRepo(), _FS(), repo).execute(
        BuildProjectGraphInput(workspace_id="w1")
    )
    graph = repo.get_latest_graph("w1")
    view = present_project_intelligence(graph, role_lens_for("developer"))
    chips = view["summary"]["technology_chips"]
    assert "FastAPI" in chips and "SQLAlchemy" in chips
    # The description now leads with the framework-aware kind (D4), not a generic
    # "Python application".
    assert "FastAPI application" in view["summary"]["description"]
