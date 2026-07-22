"""Downloading an Ollama model the way the app downloads a GGUF one.

The app already had a way to pull an Ollama model, but it was built on the
command-proposal machinery: an audit trail designed for *executing a shell
command*, which requires an approved proposal and a permission that is off by
default. An HTTP request to a daemon on localhost was being made to wear that
apparatus, and the fit was bad enough to be visible in the product — a default
build could install nothing at all through Ollama, while the llama.cpp side
downloaded gigabytes from the open internet with no ceremony.

So this is deliberately shaped like ``GgufDownloadJobRunner``: start a thread,
push progress into an in-memory job, let the API poll it. Not because symmetry
is pretty, but because the two are genuinely the same act — fetch a model from
somewhere and report how it is going — and the app should not have two different
stories about that.

The shell path is untouched. It still exists, still needs the permission, and
still only runs commands for models the app knows. See
``model_download_boundary`` for the line and why it is drawn there.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import httpx

from app.core.domain.model_download_boundary import (
    HTTP_DAEMON,
    is_valid_ollama_model_name,
    may_download,
)

# Pulling a large model over a slow link is a long wait; the connect timeout
# stays short so an unreachable daemon fails immediately rather than hanging.
_PULL_TIMEOUT = httpx.Timeout(3600.0, connect=5.0)


class OllamaModelNameInvalidError(ValueError):
    pass


class OllamaPullRefusedError(PermissionError):
    pass


@dataclass(frozen=True)
class OllamaPullJob:
    id: str
    model: str
    status: str  # queued | running | succeeded | failed | cancelled
    progress_percent: int = 0
    progress_message: str = ""
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def _percent(completed, total) -> int | None:
    try:
        done, size = int(completed), int(total)
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return None
    return max(0, min(100, round(done * 100 / size)))


class OllamaPullJobRunner:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self._base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self._jobs: dict[str, OllamaPullJob] = {}
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # -- queries ------------------------------------------------------------

    def get(self, job_id: str) -> OllamaPullJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[OllamaPullJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    # -- commands -----------------------------------------------------------

    def start(self, model_name: str) -> OllamaPullJob:
        """Begin pulling ``model_name`` through the local Ollama daemon.

        Any model the daemon can fetch is allowed. The name is validated for
        shape only — it is data we hand to an HTTP API, and refusing it for not
        being in our catalog is the restriction this whole path removes.
        """
        name = (model_name or "").strip()
        if not is_valid_ollama_model_name(name):
            raise OllamaModelNameInvalidError(
                "That does not look like an Ollama model name. Use something like "
                "'llama3.3' or 'qwen3:8b'."
            )
        permission = may_download(HTTP_DAEMON)
        if not permission.allowed:  # pragma: no cover - HTTP is always permitted
            raise OllamaPullRefusedError(permission.reason)

        job_id = uuid.uuid4().hex
        job = OllamaPullJob(
            id=job_id,
            model=name,
            status="queued",
            progress_message=f"Asking Ollama for {name}…",
        )
        cancel = threading.Event()
        with self._lock:
            self._jobs[job_id] = job
            self._cancels[job_id] = cancel
        threading.Thread(target=self._run, args=(job_id, name, cancel), daemon=True).start()
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            cancel = self._cancels.get(job_id)
            job = self._jobs.get(job_id)
        if cancel is None or job is None or job.status in ("succeeded", "failed", "cancelled"):
            return False
        cancel.set()
        self._update(job_id, status="cancelled", progress_message="Download stopped.")
        return True

    # -- internals ----------------------------------------------------------

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                return
            self._jobs[job_id] = replace(current, **changes)

    def _run(self, job_id: str, model_name: str, cancel: threading.Event) -> None:
        try:
            self._stream(job_id, model_name, cancel)
        except httpx.HTTPError as exc:
            # The daemon is the likely culprit, and saying so is more useful than
            # relaying a transport error to someone who did not ask for one.
            self._update(
                job_id,
                status="failed",
                error=(
                    f"Could not reach Ollama to download {model_name}. Is Ollama "
                    f"running? ({exc})"
                ),
                progress_message="",
            )
        except Exception as exc:  # noqa: BLE001 - a failed download must not kill the thread
            self._update(job_id, status="failed", error=str(exc), progress_message="")

    def _stream(self, job_id: str, model_name: str, cancel: threading.Event) -> None:
        last_percent = -1
        with httpx.stream(
            "POST",
            f"{self._base_url}/api/pull",
            json={"name": model_name, "stream": True},
            timeout=_PULL_TIMEOUT,
        ) as response:
            if response.status_code == 404:
                raise RuntimeError(
                    f"Ollama does not have a model called '{model_name}'. Check the "
                    f"name on ollama.com/library."
                )
            response.raise_for_status()
            self._update(job_id, status="running")
            for line in response.iter_lines():
                if cancel.is_set():
                    return
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue
                if data.get("error"):
                    raise RuntimeError(str(data["error"]))
                percent = _percent(data.get("completed"), data.get("total"))
                if percent is not None and percent != last_percent:
                    last_percent = percent
                    self._update(
                        job_id,
                        status="running",
                        progress_percent=percent,
                        progress_message=f"Downloading {model_name}: {percent}%",
                    )
                elif last_percent < 0 and data.get("status"):
                    # Ollama reports "pulling manifest" and similar before any
                    # bytes move. Showing that beats showing 0% for a minute.
                    self._update(
                        job_id, status="running", progress_message=f"{data['status']}…"
                    )
        if cancel.is_set():
            return
        self._update(
            job_id,
            status="succeeded",
            progress_percent=100,
            progress_message=f"{model_name} is ready to use.",
            error=None,
        )
