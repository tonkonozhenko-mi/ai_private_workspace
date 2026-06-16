from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_backend_startup_diagnostics_endpoint() -> None:
    response = TestClient(app).get("/runtime/frozen-backend-startup-diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["check_script"] == "scripts/check_frozen_backend_startup_diagnostics.sh"
    assert payload["smoke_script"] == "scripts/smoke_frozen_backend_runtime.sh"
    assert any(item["id"] == "import-preflight" for item in payload["diagnostics_items"])
    assert any("/health" in rule for rule in payload["safety_rules"]) or any(
        "health" in item["summary"].lower() for item in payload["diagnostics_items"]
    )


def test_frozen_backend_smoke_script_prints_log_tail_on_failure() -> None:
    script = ROOT / "scripts" / "smoke_frozen_backend_runtime.sh"
    text = script.read_text(encoding="utf-8")

    assert "print_log_tail" in text
    assert "--runtime-self-check" in text
    assert "frozen backend process exited before health became ready" in text
    assert "APP_DATA_DIR" in text
    assert "WORKSPACE_DB_PATH" in text


def test_pyinstaller_spec_collects_runtime_hidden_imports() -> None:
    spec = ROOT / "backend" / "packaging" / "ai_private_workspace_backend.spec"
    text = spec.read_text(encoding="utf-8")

    for package in ["uvicorn", "fastapi", "starlette", "pydantic", "pydantic_core", "yaml"]:
        assert f'"{package}"' in text
    assert "collect_submodules(package)" in text
    assert "datas=datas" in text
