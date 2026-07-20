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

from app.adapters.system.gguf_metadata import read_gguf_architecture
from app.adapters.system.host_memory import total_physical_ram_bytes
from app.adapters.system.llama_server_process_manager import (
    LlamaServerProcessManager,
    LlamaServerStartError,
)
from app.config.settings import resolve_llama_server_binary_path
from app.core.domain.context_window_choice import (
    expected_memory_bytes,
    MIN_CONTEXT,
    choose_context_window,
    kv_bytes_per_token,
)
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
        # The fallback window, used only when the machine won't say how much RAM it
        # has. Otherwise the window is chosen from the model and the machine.
        self._llm_context_size = llm_context_size
        # What the answer engine is actually running with, and what the model could
        # have held — both surfaced, so the number on screen is the loaded one.
        self._llm_context_running: int | None = None
        # Estimated resident cost of the answer model at the window we chose.
        self._llm_expected_bytes: int = 0
        self._llm_context_max: int | None = None
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

    def reset_model_selection(self) -> None:
        """Forget the chosen answer/search models so both resolve back to the
        recommended catalog defaults. Used on a full workspace reset: with no
        project left there is no explicit selection, so the engine must not keep
        reporting the last-lived model. Does not (re)start anything."""
        self._llm_model = None
        self._embed_model = None

    def reset_llm_selection(self) -> None:
        """Forget only the chosen answer model so it resolves back to the
        recommended catalog default; leaves the search/embedding model untouched
        (changing that would invalidate an existing index). Used when a workspace
        activates with no explicit answer-model choice, so the engine doesn't
        inherit a stale last-loaded model. Does not (re)start anything."""
        self._llm_model = None

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
            "models_ready": self._dl.is_installed(llm_model) and self._dl.is_installed(embed_model),
            "running": running,
            "active_llm_model": llm_model.id,
            "active_embedding_model": embed_model.id,
            # The window the answer engine actually loaded, and the one the model
            # could have held — so the Models card can say which of the two limits
            # is doing the limiting: this machine, or the model itself.
            "llm_context_tokens": self._llm_context_running if running else None,
            "llm_expected_bytes": self._llm_expected_bytes if running else 0,
            "llm_context_max_tokens": self._llm_context_max,
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

    def _choose_llm_context(self, model: GgufModel) -> tuple[int, int | None]:
        """The window to run this answer model with, and the window it could hold.

        Read from the model file itself (layers, heads — what a token of context
        costs) and from the machine (how much of that we can afford). A model with
        a 131k paper window on a 16 GB laptop gets 16k, not a shrug and a fixed
        8192.
        """
        path = self._dl.destination_path(model)
        architecture = read_gguf_architecture(path)
        try:
            file_bytes = os.path.getsize(path)
        except OSError:
            file_bytes = model.size_bytes or 0
        total_ram = total_physical_ram_bytes()
        if total_ram <= 0:
            # The OS won't say how much memory it has: keep today's behaviour
            # rather than gamble with someone else's machine.
            return self._llm_context_size, (architecture.context_length if architecture else None)
        cost = kv_bytes_per_token(
            block_count=architecture.block_count if architecture else None,
            head_count_kv=architecture.head_count_kv if architecture else None,
            embedding_length=architecture.embedding_length if architecture else None,
            head_count=architecture.head_count if architecture else None,
            model_file_bytes=file_bytes,
        )
        model_max = (architecture.context_length if architecture else None) or 0
        chosen = choose_context_window(
            model_max_context=model_max,
            kv_bytes_per_token=cost,
            total_ram_bytes=total_ram,
            model_file_bytes=file_bytes,
        )
        # What this choice costs in memory, kept so the app can say it before a
        # person waits rather than only measuring it once they have. Same two
        # numbers the choice was made from; no second source to disagree with.
        self._llm_expected_bytes = expected_memory_bytes(
            model_file_bytes=file_bytes,
            kv_bytes_per_token=cost,
            context_window=chosen,
        )
        return chosen, (model_max or None)

    def _start_llm_server(self, binary, model: GgufModel) -> LlamaServerProcessManager:
        """Start the answer engine, stepping the window down if it won't fit.

        The arithmetic says the window is affordable; the machine has the last
        word. If llama-server won't come up (the KV cache is the usual reason),
        halve the window and try again, down to the 8192 that has always worked.
        Each step says why in the log, so a small window is never a mystery.
        """
        chosen, model_max = self._choose_llm_context(model)
        self._llm_context_max = model_max
        path = self._dl.destination_path(model)
        context = chosen
        last_error: LlamaServerStartError | None = None
        while context >= MIN_CONTEXT:
            server = LlamaServerProcessManager(binary, host=self._host, context_size=context)
            try:
                server.start(path, self._llm_port)
            except LlamaServerStartError as exc:
                last_error = exc
                server.stop()
                if context == MIN_CONTEXT:
                    break
                context = max(MIN_CONTEXT, context // 2)
                print(
                    f"[llama] {model.id} did not start with a {chosen:,}-token window "
                    f"({exc}); retrying with {context:,}.",
                    flush=True,
                )
                continue
            self._llm_context_running = context
            return server
        self._llm_context_running = None
        raise LlamaRuntimeError(
            f"The answer engine could not start even with the smallest window "
            f"({MIN_CONTEXT:,} tokens): {last_error}"
        )

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
            self._llm = self._start_llm_server(binary, llm_model)
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
            # A different model has a different appetite per token, so the window is
            # chosen again rather than inherited from the model we just stopped.
            self._llm = self._start_llm_server(binary, model)
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
            self._embed.start(self._dl.destination_path(model), self._embed_port, embedding=True)
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
