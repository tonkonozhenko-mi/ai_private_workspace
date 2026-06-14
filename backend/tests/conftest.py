import os
from pathlib import Path
import sys
import tempfile


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
