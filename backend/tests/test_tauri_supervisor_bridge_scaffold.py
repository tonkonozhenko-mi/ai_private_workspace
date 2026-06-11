from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_tauri_supervisor_bridge_commands_are_scaffolded_without_shell_execution() -> None:
    main_rs = (ROOT / "frontend" / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")

    assert "get_supervisor_status" in main_rs
    assert "get_supervisor_log_paths" in main_rs
    assert "std::process::Command" not in main_rs
    assert "Command::new" not in main_rs
    assert "ollama pull" not in main_rs
    assert "uvicorn" not in main_rs


def test_tauri_scaffold_config_exists_for_desktop_shell() -> None:
    assert (ROOT / "frontend" / "src-tauri" / "tauri.conf.json").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "Cargo.toml").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "build.rs").is_file()
