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
