from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

def repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text()


def test_packaged_runtime_defaults_to_sqlite_vector_store():
    entrypoint = repo_file("backend/packaging/pyinstaller_backend_entrypoint.py")
    tauri = repo_file("frontend/src-tauri/src/lib.rs")

    assert 'os.environ.setdefault("VECTOR_STORE", "sqlite")' in entrypoint
    assert '.env("VECTOR_STORE", "sqlite")' in tauri
    assert "VECTOR_STORE=memory" not in tauri


def test_packaged_runtime_uses_app_owned_vector_store_path():
    entrypoint = repo_file("backend/packaging/pyinstaller_backend_entrypoint.py")
    tauri = repo_file("frontend/src-tauri/src/lib.rs")

    assert 'default=app_data_dir / "data" / "vector_store.db"' in entrypoint
    assert 'app_data_dir().join("data").join("vector_store.db")' in tauri
    assert '.env("VECTOR_STORE_PATH", vector_store_path())' in tauri
    assert 'os.environ["VECTOR_STORE_PATH"] = str(vector_store_path)' in entrypoint
    assert ".app/Contents/Resources" not in entrypoint


def test_sqlite_vector_store_provider_is_registered():
    dependencies = repo_file("backend/app/api/dependencies.py")
    settings = repo_file("backend/app/config/settings.py")

    assert "SQLiteVectorStore" in dependencies
    assert 'if vector_store_type == "sqlite"' in dependencies
    assert "VECTOR_STORE_PATH" in settings
    assert "AI_WORKSPACE_VECTOR_STORE_PATH" in settings
