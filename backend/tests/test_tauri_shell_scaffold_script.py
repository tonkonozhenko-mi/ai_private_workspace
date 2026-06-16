from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_tauri_scaffold_files_exist() -> None:
    assert (ROOT / "frontend" / "src-tauri" / "tauri.conf.json").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "Cargo.toml").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "build.rs").is_file()
    assert (ROOT / "frontend" / "src-tauri" / "src" / "main.rs").is_file()
    assert (ROOT / "scripts" / "prepare_tauri_shell_scaffold.sh").is_file()


def test_tauri_entrypoint_does_not_execute_processes() -> None:
    main_rs = (ROOT / "frontend" / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")

    assert "std::process::Command" not in main_rs
    assert "Command::new" not in main_rs
    assert "ollama pull" not in main_rs
    assert "scan" not in main_rs.lower() or "No scan" in main_rs
