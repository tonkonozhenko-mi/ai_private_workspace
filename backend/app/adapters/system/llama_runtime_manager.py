"""Orchestrate the local llama.cpp runtime: one ``llama-server`` for answers and
one (``--embedding``) for search, started from the bundled binary against the
downloaded GGUF models.

Everything degrades gracefully: if the binary is not bundled (e.g. a local
Ollama-only build) or the models are not downloaded yet, ``start`` raises a
clear error and the app stays on Ollama. Nothing here runs unless the user picks
the llama.cpp backend.
"""

import subprocess
import threading

from app.adapters.system.llama_server_process_manager import LlamaServerProcessManager
from app.config.settings import resolve_llama_server_binary_path
from app.core.domain.gguf_catalog import (
    GgufModel,
    default_gguf_embedding,
    default_gguf_llm,
)
from app.core.use_cases.download_gguf_model import (
    DownloadGgufModelUseCase,
    GgufModelNotResolvedError,
    GgufModelRef,
    resolve_gguf_model,
)


class LlamaRuntimeError(RuntimeError):
    pass


def _process_rss_bytes(pid: int) -> int:
    """Resident set size of a process in bytes, via ``ps`` (KB → bytes).

    Returns 0 if the process is gone or ``ps`` is unavailable. macOS and Linux
    both support ``ps -o rss= -p <pid>`` (kilobytes).
    """
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    raw = out.stdout.strip()
    if not raw.isdigit():
        return 0
    return int(raw) * 1024


class LlamaRuntimeManager:
    def __init__(
        self,
        download_use_case: DownloadGgufModelUseCase,
        host: str = "127.0.0.1",
        llm_port: int = 8080,
        embed_port: int = 8081,
    ) -> None:
        self._dl = download_use_case
        self._host = host
        self._llm_port = llm_port
        self._embed_port = embed_port
        self._llm: LlamaServerProcessManager | None = None
        self._embed: LlamaServerProcessManager | None = None
        self._llm_model: GgufModel | None = None
        self._lock = threading.Lock()

    def _running(self) -> bool:
        return (
            self._llm is not None
            and self._llm.is_running()
            and self._embed is not None
            and self._embed.is_running()
        )

    def _resolve_llm_model(self) -> GgufModel:
        """The chosen answer model, or the recommended default if none/invalid."""
        return self._llm_model or default_gguf_llm()

    def set_llm_ref(self, ref: GgufModelRef | None) -> None:
        """Remember which answer model to run (catalog id or custom repo/file).

        Does not (re)start anything — ``start``/``switch_llm`` use it. Invalid
        refs are ignored, so a stale persisted choice can never break startup.
        """
        if ref is None:
            return
        try:
            self._llm_model = resolve_gguf_model(ref)
        except GgufModelNotResolvedError:
            pass

    @property
    def active_llm_model_id(self) -> str:
        return self._resolve_llm_model().id

    def status(self) -> dict:
        binary = resolve_llama_server_binary_path()
        llm_model = self._resolve_llm_model()
        embed_model = default_gguf_embedding()
        running = self._running()
        return {
            "binary_available": binary is not None,
            "binary_path": str(binary) if binary is not None else None,
            "models_ready": self._dl.is_installed(llm_model)
            and self._dl.is_installed(embed_model),
            "running": running,
            "active_llm_model": llm_model.id,
            "llm_url": f"http://{self._host}:{self._llm_port}" if running else None,
            "embed_url": f"http://{self._host}:{self._embed_port}" if running else None,
        }

    def start(self) -> dict:
        binary = resolve_llama_server_binary_path()
        if binary is None:
            raise LlamaRuntimeError(
                "The llama.cpp engine is not bundled in this build yet. "
                "Run scripts/fetch_llama_server.sh or use a packaged release."
            )
        llm_model = self._resolve_llm_model()
        embed_model = default_gguf_embedding()
        if not self._dl.is_installed(llm_model):
            raise LlamaRuntimeError("The answer model has not been downloaded yet.")
        if not self._dl.is_installed(embed_model):
            raise LlamaRuntimeError("The search model has not been downloaded yet.")

        with self._lock:
            if self._running():
                return self.status()
            self._llm = LlamaServerProcessManager(binary, host=self._host)
            self._llm.start(self._dl.destination_path(llm_model), self._llm_port)
            self._embed = LlamaServerProcessManager(binary, host=self._host)
            self._embed.start(
                self._dl.destination_path(embed_model), self._embed_port, embedding=True
            )
        return self.status()

    def switch_llm(self, ref: GgufModelRef) -> dict:
        """Restart only the answer engine on a different (already downloaded) model.

        Accepts a catalog id or a custom Hugging Face repo/file. Search/embeddings
        keep running untouched. Raises ``LlamaRuntimeError`` if the model cannot be
        resolved or is not downloaded yet.
        """
        try:
            model = resolve_gguf_model(ref)
        except GgufModelNotResolvedError as exc:
            raise LlamaRuntimeError(str(exc)) from exc
        if not self._dl.is_installed(model):
            raise LlamaRuntimeError("That answer model has not been downloaded yet.")
        binary = resolve_llama_server_binary_path()
        if binary is None:
            raise LlamaRuntimeError("The llama.cpp engine is not bundled in this build.")

        with self._lock:
            self._llm_model = model
            if self._llm is not None:
                self._llm.stop()
            self._llm = LlamaServerProcessManager(binary, host=self._host)
            self._llm.start(self._dl.destination_path(model), self._llm_port)
        return self.status()

    def memory(self) -> list[dict]:
        """Resident memory of the running llama-server processes (answer + search).

        Read-only. Returns [] when nothing is running. RSS is read via ``ps`` so
        no extra dependency (psutil) is needed and it works in the packaged app.
        """
        entries: list[dict] = []
        labels = (self._resolve_llm_model().id, default_gguf_embedding().id)
        for label, mgr in zip(labels, (self._llm, self._embed)):
            pid = mgr.pid if mgr is not None else None
            if pid is None:
                continue
            rss = _process_rss_bytes(pid)
            if rss > 0:
                entries.append({"name": f"llamacpp/{label}", "rss_bytes": rss})
        return entries

    def stop(self) -> dict:
        with self._lock:
            if self._llm is not None:
                self._llm.stop()
            if self._embed is not None:
                self._embed.stop()
        return self.status()
