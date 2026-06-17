"""Launch and supervise a bundled ``llama-server`` (llama.cpp) process.

One ``llama-server`` serves one model, so the app runs two: one for answers and
one (started with ``--embedding``) for search embeddings — exactly how Ollama
spawns a llama.cpp runner per loaded model under the hood.

This manager only starts/health-checks/stops the process. The binary itself is
bundled with the app (per arch) and never downloaded at runtime; the GGUF model
files are downloaded separately. Nothing here runs unless the user has chosen
the llama.cpp backend.
"""

import subprocess
import time
from pathlib import Path

import httpx


class LlamaServerStartError(RuntimeError):
    pass


class LlamaServerProcessManager:
    def __init__(
        self,
        binary_path: str | Path,
        host: str = "127.0.0.1",
        context_size: int = 4096,
        startup_timeout_seconds: int = 60,
    ) -> None:
        self.binary_path = Path(binary_path)
        self.host = host
        self.context_size = context_size
        self.startup_timeout_seconds = startup_timeout_seconds
        self._process: subprocess.Popen | None = None
        self._port: int | None = None

    @property
    def base_url(self) -> str | None:
        if self._port is None:
            return None
        return f"http://{self.host}:{self._port}"

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, model_path: str | Path, port: int, embedding: bool = False) -> str:
        """Start llama-server for ``model_path`` on ``port``; return the base URL."""
        if not self.binary_path.is_file():
            raise LlamaServerStartError(
                f"llama-server binary not found at {self.binary_path}. It must be "
                "bundled with the app for this architecture."
            )
        model = Path(model_path)
        if not model.is_file():
            raise LlamaServerStartError(f"Model file not found: {model}")

        args = [
            str(self.binary_path),
            "-m",
            str(model),
            "--host",
            self.host,
            "--port",
            str(port),
            "-c",
            str(self.context_size),
            # Apply the model's own chat template from GGUF metadata, so turns end
            # cleanly and special tokens (<|eot_id|>, …) are not emitted as text.
            "--jinja",
        ]
        if embedding:
            args.append("--embedding")

        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except OSError as exc:
            raise LlamaServerStartError(f"Could not launch llama-server: {exc}") from exc

        self._port = port
        self._wait_until_healthy()
        return f"http://{self.host}:{port}"

    def _wait_until_healthy(self) -> None:
        url = f"{self.base_url}/health"
        deadline = time.monotonic() + self.startup_timeout_seconds
        while time.monotonic() < deadline:
            if not self.is_running():
                raise LlamaServerStartError("llama-server exited during startup")
            try:
                response = httpx.get(url, timeout=2)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        self.stop()
        raise LlamaServerStartError(
            f"llama-server did not become healthy within {self.startup_timeout_seconds}s"
        )

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._port = None
