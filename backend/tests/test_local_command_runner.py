from app.adapters.commands.fake_command_runner import FakeCommandRunner
from app.adapters.commands.local_command_runner import LocalCommandRunner
from app.api.dependencies import build_command_runner
from app.config.settings import get_settings


def test_local_command_runner_runs_pwd_inside_allowed_root(tmp_path) -> None:
    runner = LocalCommandRunner()

    result = runner.run(
        command="pwd",
        cwd=str(tmp_path),
        allowed_root=str(tmp_path),
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == str(tmp_path.resolve())
    assert result.stderr == ""


def test_local_command_runner_rejects_cwd_outside_allowed_root(tmp_path) -> None:
    allowed_root = tmp_path / "workspace"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()
    runner = LocalCommandRunner()

    result = runner.run(
        command="pwd",
        cwd=str(outside_root),
        allowed_root=str(allowed_root),
    )

    assert result.exit_code == 126
    assert result.stderr == "Working directory is outside the allowed workspace root."


def test_local_command_runner_executable_not_found_returns_127(tmp_path) -> None:
    runner = LocalCommandRunner()

    result = runner.run(
        command="definitely-not-a-real-command",
        cwd=str(tmp_path),
        allowed_root=str(tmp_path),
    )

    assert result.exit_code == 127
    assert result.stderr == "Executable not found: definitely-not-a-real-command"


def test_build_command_runner_uses_fake_by_default(monkeypatch) -> None:
    monkeypatch.delenv("COMMAND_RUNNER", raising=False)
    get_settings.cache_clear()

    runner = build_command_runner()

    assert isinstance(runner, FakeCommandRunner)
    get_settings.cache_clear()


def test_build_command_runner_can_enable_local_runner(monkeypatch) -> None:
    monkeypatch.setenv("COMMAND_RUNNER", "local")
    monkeypatch.setenv("COMMAND_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("COMMAND_OUTPUT_LIMIT_CHARS", "100")
    get_settings.cache_clear()

    runner = build_command_runner()

    assert isinstance(runner, LocalCommandRunner)
    assert runner.timeout_seconds == 5
    assert runner.output_limit_chars == 100
    get_settings.cache_clear()
