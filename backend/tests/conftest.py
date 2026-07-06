import os
import sys
import tempfile
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

test_data_dir = Path(tempfile.mkdtemp(prefix="ai-workbench-tests-"))
os.environ["APP_DATA_DIR"] = str(test_data_dir)
os.environ["WORKSPACE_DB_PATH"] = str(test_data_dir / "workspaces.db")
os.environ["WORKSPACE_REPOSITORY"] = "sqlite"

# Keep the full test suite deterministic even if the developer shell is configured
# for the real local runtime. Individual tests can still override these values
# with monkeypatch after conftest is loaded.
os.environ["VECTOR_STORE"] = "memory"
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["EMBEDDING_MODEL"] = "fake-embedding-model"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["LLM_MODEL"] = "fake-llm"
os.environ["COMMAND_RUNNER"] = "fake"
os.environ["MODEL_DOWNLOAD_EXECUTION_ENABLED"] = "false"
# Pin runtime defaults so a developer shell or backend/.env (Ollama host, custom
# model catalog) cannot leak into the deterministic test environment.
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["USER_MODEL_CATALOG_PATH"] = str(test_data_dir / "user-model-catalog.json")

# The packaged backend raises its open-file limit during FastAPI lifespan
# startup (app/config/fd_limit.py) — but module-level TestClient instances
# never run that lifespan, so the suite otherwise executes under macOS's
# default 256-descriptor ceiling. Under that ceiling, WAL's extra file
# handles (-wal/-shm) plus the connections pinned alive by pytest's kept
# failure tracebacks can cascade into "unable to open database file" for
# every later test that touches the shared session database (observed live:
# one real assertion failure snowballed into 12 unrelated OperationalErrors).
# Mirror production so tests run with the same headroom the app has.
from app.config.fd_limit import raise_fd_limit  # noqa: E402

raise_fd_limit()
