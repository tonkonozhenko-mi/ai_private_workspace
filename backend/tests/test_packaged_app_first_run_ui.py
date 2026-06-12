from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_packaged_app_first_run_ui_check_script_exists_and_is_strict() -> None:
    script = ROOT / "scripts" / "check_packaged_app_first_run_ui.sh"

    assert script.exists()
    assert script.stat().st_mode & 0o111
    text = script.read_text(encoding="utf-8")
    assert "loadWorkspacesRequestIdRef" in text
    assert "waitForBackendApi" in text
    assert "desktop-startup-banner" in text
    assert "No projects yet" in text
    assert "desktop-supervisor.log" in text


def test_packaged_app_first_run_ui_source_clears_stale_backend_errors() -> None:
    app_tsx = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "loadWorkspacesRequestIdRef" in app_tsx
    assert "waitForBackendApi" in app_tsx
    assert "setWorkspacesError(null);" in app_tsx
    assert "desktop-startup-banner" in app_tsx
    assert "No projects yet" in app_tsx
    assert "The desktop backend is running" in app_tsx
    assert "Desktop backend did not become reachable" in app_tsx
