"""Launch and supervise a bundled ``llama-server`` (llama.cpp) process.

One ``llama-server`` serves one model, so the app runs two: one for answers and
one (started with ``--embedding``) for search embeddings — exactly how Ollama
spawns a llama.cpp runner per loaded model under the hood.

This manager only starts/health-checks/stops the process. The binary itself is
bundled with the app (per arch) and never downloaded at runtime; the GGUF model
files are downloaded separately. Nothing here runs unless the user has chosen
the llama.cpp backend.
"""

import os
import subprocess
import tempfile
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
        self._log_path: Path | None = None

    @property
    def base_url(self) -> str | None:
        if self._port is None:
            return None
        return f"http://{self.host}:{self._port}"

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def pid(self) -> int | None:
        if self._process is not None and self._process.poll() is None:
            return self._process.pid
        return None

    def start(
        self,
        model_path: str | Path,
        port: int,
        embedding: bool = False,
        reranking: bool = False,
    ) -> str:
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
        ]
        if reranking or embedding:
            # Embedding/reranking process the whole input in one pass with pooling,
            # so the entire input must fit in a single *physical* batch. The
            # default ubatch is 512, which makes llama-server return HTTP 500
            # ("input is too large to process. increase the physical batch size")
            # for longer chunks. Size the batch to the context so any chunk fits.
            args += ["-b", str(self.context_size), "-ub", str(self.context_size)]
        if reranking:
            # A cross-encoder reranker server: `--reranking` enables the /rerank
            # endpoint. No chat template, so `--jinja` is omitted.
            args.append("--reranking")
        elif embedding:
            # An embedding server needs pooling enabled, otherwise `/v1/embeddings`
            # returns HTTP 500 for many GGUFs whose metadata pooling type is
            # "none". `mean` is the safe default for sentence embeddings. It does
            # not need a chat template, so `--jinja` is intentionally omitted.
            args += ["--embedding", "--pooling", "mean"]
        else:
            # Apply the model's own chat template from GGUF metadata, so turns end
            # cleanly and special tokens (<|eot_id|>, …) are not emitted as text.
            args.append("--jinja")

        # The prebuilt llama.cpp binary ships its dylibs alongside it. Point the
        # dynamic loader at that folder so the libraries resolve regardless of
        # how the binary's rpath was baked, and run from there for good measure.
        lib_dir = str(self.binary_path.parent)
        env = os.environ.copy()
        if os.name == "nt":
            # Windows resolves a binary's DLLs from PATH (and the exe's own dir).
            # The prebuilt llama.cpp ships its DLLs next to llama-server.exe, so
            # prepend that folder to PATH with the Windows separator.
            existing_path = env.get("PATH", "")
            env["PATH"] = f"{lib_dir};{existing_path}" if existing_path else lib_dir
        else:
            for key in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
                existing = env.get(key)
                env[key] = f"{lib_dir}:{existing}" if existing else lib_dir

        # Capture stdout+stderr to a log file so a startup failure surfaces the
        # actual llama.cpp error (missing dylib, bad flag, model load failure…)
        # instead of an opaque "exited during startup".
        log_handle = tempfile.NamedTemporaryFile(
            mode="w+", suffix="-llama-server.log", delete=False
        )
        self._log_path = Path(log_handle.name)
        try:
            self._process = subprocess.Popen(
                args,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
                cwd=lib_dir,
                env=env,
            )
        except OSError as exc:
            log_handle.close()
            raise LlamaServerStartError(f"Could not launch llama-server: {exc}") from exc
        finally:
            log_handle.close()

        self._port = port
        self._wait_until_healthy()
        return f"http://{self.host}:{port}"

    def _log_tail(self, max_chars: int = 600) -> str:
        try:
            text = self._log_path.read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, AttributeError):
            return ""
        return text[-max_chars:] if text else ""

    def _wait_until_healthy(self) -> None:
        url = f"{self.base_url}/health"
        deadline = time.monotonic() + self.startup_timeout_seconds
        while time.monotonic() < deadline:
            if not self.is_running():
                detail = self._log_tail()
                raise LlamaServerStartError(
                    "llama-server exited during startup"
                    + (f": {detail}" if detail else "")
                )
            try:
                response = httpx.get(url, timeout=2)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        detail = self._log_tail()
        self.stop()
        raise LlamaServerStartError(
            f"llama-server did not become healthy within {self.startup_timeout_seconds}s"
            + (f": {detail}" if detail else "")
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
