from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_tauri_supervisor_bridge_commands_are_scaffolded_without_shell_execution() -> None:
    lib_rs = (ROOT / "frontend" / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    main_rs = (ROOT / "frontend" / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")

    assert "get_supervisor_status" in lib_rs
    assert "get_supervisor_log_paths" in lib_rs
    assert "ai_private_workspace_lib::run()" in main_rs
    assert "Command::new" in lib_rs
    assert "sh -c" not in lib_rs
    assert "cmd /C" not in lib_rs
    assert "ollama pull" not in lib_rs
    assert "uvicorn" not in lib_rs


def test_tauri_scaffold_config_exists_for_desktop_shell() -> None:
    assert (ROOT / "frontend" / "src-tauri" / "tauri.conf.json").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "Cargo.toml").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "build.rs").is_file()
