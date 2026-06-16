import shlex
import subprocess
from pathlib import Path

from app.core.ports.command_runner import CommandResult


class LocalCommandRunner:
    def __init__(
        self,
        timeout_seconds: int = 30,
        output_limit_chars: int = 20000,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.output_limit_chars = output_limit_chars

    def run(
        self,
        command: str,
        cwd: str,
        allowed_root: str | None = None,
    ) -> CommandResult:
        cwd_path = Path(cwd).resolve()
        allowed_root_path = Path(allowed_root or cwd).resolve()

        if not cwd_path.exists() or not cwd_path.is_dir():
            return self._error(command, "Working directory does not exist or is not a directory.")

        try:
            cwd_path.relative_to(allowed_root_path)
        except ValueError:
            return self._error(command, "Working directory is outside the allowed workspace root.")

        try:
            args = shlex.split(command)
        except ValueError as exc:
            return self._error(command, f"Unable to parse command: {exc}")

        if not args:
            return self._error(command, "Command is empty.")

        try:
            completed_process = subprocess.run(
                args,
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._limit_output(exc.stdout or "")
            stderr = self._limit_output(f"Command timed out after {self.timeout_seconds} seconds.")
            return CommandResult(
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=124,
            )
        except FileNotFoundError:
            return CommandResult(
                command=command,
                stdout="",
                stderr=f"Executable not found: {args[0]}",
                exit_code=127,
            )

        return CommandResult(
            command=command,
            stdout=self._limit_output(completed_process.stdout),
            stderr=self._limit_output(completed_process.stderr),
            exit_code=completed_process.returncode,
        )

    def _error(self, command: str, stderr: str) -> CommandResult:
        return CommandResult(
            command=command,
            stdout="",
            stderr=stderr,
            exit_code=126,
        )

    def _limit_output(self, output: str) -> str:
        return output[: self.output_limit_chars]
