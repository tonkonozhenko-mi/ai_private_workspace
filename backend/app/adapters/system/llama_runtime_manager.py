"""Orchestrate the local llama.cpp runtime: one ``llama-server`` for answers and
one (``--embedding``) for search, started from the bundled binary against the
downloaded GGUF models.

Everything degrades gracefully: if the binary is not bundled (e.g. a local
Ollama-only build) or the models are not downloaded yet, ``start`` raises a
clear error and the app stays on Ollama. Nothing here runs unless the user picks
the llama.cpp backend.
"""

import os
import signal
import subprocess
import threading
import time

from app.adapters.system.llama_server_process_manager import LlamaServerProcessManager
from app.config.settings import resolve_llama_server_binary_path
from app.core.domain.gguf_catalog import (
    GgufModel,
    default_gguf_embedding,
    default_gguf_llm,
    default_gguf_reranker,
)
from app.core.use_cases.download_gguf_model import (
    DownloadGgufModelUseCase,
    GgufModelNotResolvedError,
    GgufModelRef,
    resolve_gguf_model,
)


class LlamaRuntimeError(RuntimeError):
    pass


def _reap_orphan_llama_servers(binary_path: str) -> None:
    """Kill leftover llama-server processes from a previous app run.

    A child process is NOT killed when its parent (the backend) exits, so a
    previous run can leave a ``llama-server`` still holding ports 8080/8081,
    making the new server fail to bind ("couldn't bind HTTP server socket") and
    requests hit the stale instance (HTTP 500).

    We match the EXACT bundled binary path, so this only ever touches our own
    orphaned llama-server instances — never unknown processes on those ports.
    Called only before a fresh start, when this backend owns no live children.
    """
    if os.name == "nt":
        _reap_orphan_llama_servers_windows(binary_path)
    else:
        _reap_orphan_llama_servers_unix(binary_path)


def _reap_orphan_llama_servers_unix(binary_path: str) -> None:
    try:
        result = subprocess.run(
            ["pgrep", "-f", binary_path],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return
    own_pid = os.getpid()
    pids = [int(line) for line in result.stdout.split() if line.isdigit() and int(line) != own_pid]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    if pids:
        time.sleep(0.5)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def _reap_orphan_llama_servers_windows(binary_path: str) -> None:
    """Windows equivalent: match processes by their exact executable path via
    PowerShell CIM (the same "only ever our own binary" guarantee pgrep gives on
    Unix), then force-stop them. Best-effort — any failure is ignored."""
    own_pid = os.getpid()
    # Single-quote the path for PowerShell (literal string; backslashes are fine).
    safe_path = binary_path.replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.ExecutablePath -eq '{safe_path}' -and $_.ProcessId -ne {own_pid} "
        "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return


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
        rerank_port: int = 8082,
        llm_context_size: int = 8192,
    ) -> None:
        self._dl = download_use_case
        self._host = host
        self._llm_port = llm_port
        self._embed_port = embed_port
        self._rerank_port = rerank_port
        self._llm_context_size = llm_context_size
        self._llm: LlamaServerProcessManager | None = None
        self._embed: LlamaServerProcessManager | None = None
        self._rerank: LlamaServerProcessManager | None = None
        self._llm_model: GgufModel | None = None
        self._embed_model: GgufModel | None = None
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

    def _resolve_embed_model(self) -> GgufModel:
        """The chosen search model, or the recommended default if none/invalid."""
        return self._embed_model or default_gguf_embedding()

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

    def set_embed_ref(self, ref: GgufModelRef | None) -> None:
        """Remember which search/embedding model to run. Like ``set_llm_ref``:
        does not (re)start anything, and ignores invalid refs."""
        if ref is None:
            return
        try:
            self._embed_model = resolve_gguf_model(ref)
        except GgufModelNotResolvedError:
            pass

    @property
    def active_llm_model_id(self) -> str:
        return self._resolve_llm_model().id

    @property
    def active_embed_model_id(self) -> str:
        return self._resolve_embed_model().id

    def _rerank_running(self) -> bool:
        return self._rerank is not None and self._rerank.is_running()

    @property
    def rerank_url(self) -> str:
        return f"http://{self._host}:{self._rerank_port}"

    def status(self) -> dict:
        binary = resolve_llama_server_binary_path()
        llm_model = self._resolve_llm_model()
        embed_model = self._resolve_embed_model()
        rerank_model = default_gguf_reranker()
        running = self._running()
        rerank_running = self._rerank_running()
        return {
            "binary_available": binary is not None,
            "binary_path": str(binary) if binary is not None else None,
            "models_ready": self._dl.is_installed(llm_model)
            and self._dl.is_installed(embed_model),
            "running": running,
            "active_llm_model": llm_model.id,
            "active_embedding_model": embed_model.id,
            "llm_url": f"http://{self._host}:{self._llm_port}" if running else None,
            "embed_url": f"http://{self._host}:{self._embed_port}" if running else None,
            # Reranker is an optional "sharper search" precision pass (llama.cpp).
            "rerank_model_id": rerank_model.id,
            "rerank_model_installed": self._dl.is_installed(rerank_model),
            "rerank_running": rerank_running,
            "rerank_url": self.rerank_url if rerank_running else None,
        }

    def enable_rerank(self) -> dict:
        """Download-gated: starts the reranker server if its model is installed.

        Raises ``LlamaRuntimeError`` if the binary or model is missing, so the UI
        can prompt a download. The main answer/search runtime is untouched.
        """
        binary = resolve_llama_server_binary_path()
        if binary is None:
            raise LlamaRuntimeError("The llama.cpp engine is not bundled in this build.")
        rerank_model = default_gguf_reranker()
        if not self._dl.is_installed(rerank_model):
            raise LlamaRuntimeError("The reranker model has not been downloaded yet.")
        with self._lock:
            if self._rerank_running():
                return self.status()
            self._rerank = LlamaServerProcessManager(binary, host=self._host)
            self._rerank.start(
                self._dl.destination_path(rerank_model),
                self._rerank_port,
                reranking=True,
            )
        return self.status()

    def disable_rerank(self) -> dict:
        with self._lock:
            if self._rerank is not None:
                self._rerank.stop()
                self._rerank = None
        return self.status()

    def start(self) -> dict:
        binary = resolve_llama_server_binary_path()
        if binary is None:
            raise LlamaRuntimeError(
                "The llama.cpp engine is not bundled in this build yet. "
                "Run scripts/fetch_llama_server.sh or use a packaged release."
            )
        llm_model = self._resolve_llm_model()
        embed_model = self._resolve_embed_model()
        if not self._dl.is_installed(llm_model):
            raise LlamaRuntimeError("The answer model has not been downloaded yet.")
        if not self._dl.is_installed(embed_model):
            raise LlamaRuntimeError("The search model has not been downloaded yet.")

        with self._lock:
            if self._running():
                return self.status()
            # Fresh start (this backend owns no live servers): clear any orphaned
            # llama-server from a previous app run that may still hold our ports,
            # otherwise the new servers fail to bind and requests hit a stale one.
            if self._llm is None and self._embed is None and self._rerank is None:
                _reap_orphan_llama_servers(str(binary))
            self._llm = LlamaServerProcessManager(
                binary, host=self._host, context_size=self._llm_context_size
            )
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
            self._llm = LlamaServerProcessManager(
                binary, host=self._host, context_size=self._llm_context_size
            )
            self._llm.start(self._dl.destination_path(model), self._llm_port)
        return self.status()

    def switch_embedding(self, ref: GgufModelRef) -> dict:
        """Restart only the search/embedding engine on a different (already
        downloaded) model. The answer model keeps running untouched. The caller is
        responsible for rebuilding the index, since a different embedder produces a
        different vector space."""
        try:
            model = resolve_gguf_model(ref)
        except GgufModelNotResolvedError as exc:
            raise LlamaRuntimeError(str(exc)) from exc
        if model.model_type != "embedding":
            raise LlamaRuntimeError("That model is not a search/embedding model.")
        if not self._dl.is_installed(model):
            raise LlamaRuntimeError("That search model has not been downloaded yet.")
        binary = resolve_llama_server_binary_path()
        if binary is None:
            raise LlamaRuntimeError("The llama.cpp engine is not bundled in this build.")

        with self._lock:
            self._embed_model = model
            if self._embed is not None:
                self._embed.stop()
            self._embed = LlamaServerProcessManager(binary, host=self._host)
            self._embed.start(
                self._dl.destination_path(model), self._embed_port, embedding=True
            )
        return self.status()

    def memory(self) -> list[dict]:
        """Resident memory of the running llama-server processes (answer + search).

        Read-only. Returns [] when nothing is running. RSS is read via ``ps`` so
        no extra dependency (psutil) is needed and it works in the packaged app.
        """
        entries: list[dict] = []
        labels = (
            self._resolve_llm_model().id,
            self._resolve_embed_model().id,
            default_gguf_reranker().id,
        )
        for label, mgr in zip(labels, (self._llm, self._embed, self._rerank)):
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
            if self._rerank is not None:
                self._rerank.stop()
                self._rerank = None
        return self.status()
