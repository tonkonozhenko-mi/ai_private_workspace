"""In-process runner for background GGUF model downloads.

Each download runs on a daemon thread; progress is pushed into an in-memory
:class:`GgufDownloadJob` that the API polls, and a per-job cancel event lets the
user stop a multi-GB download cleanly. The underlying downloader writes to a
``.part`` temp file and only publishes the final model on success, so a cancel
never leaves a half-written model.
"""

import threading
import uuid

from app.core.domain.gguf_catalog import GgufModel
from app.core.domain.gguf_download_job import GgufDownloadJob
from app.core.ports.gguf_downloader import GgufDownloadCancelledError
from app.core.use_cases.download_gguf_model import (
    DownloadGgufModelUseCase,
    GgufModelRef,
    resolve_gguf_model,
)


class GgufDownloadJobRunner:
    def __init__(self, use_case: DownloadGgufModelUseCase) -> None:
        self._use_case = use_case
        self._jobs: dict[str, GgufDownloadJob] = {}
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # -- queries ------------------------------------------------------------

    def get(self, job_id: str) -> GgufDownloadJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[GgufDownloadJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    # -- commands -----------------------------------------------------------

    def start(self, ref: GgufModelRef) -> GgufDownloadJob:
        model: GgufModel = resolve_gguf_model(ref)
        job_id = uuid.uuid4().hex
        job = GgufDownloadJob(
            id=job_id,
            model_id=model.id,
            name=model.name,
            model_type=model.model_type,
            total_bytes=model.size_bytes or None,
        )
        cancel_event = threading.Event()
        with self._lock:
            self._jobs[job_id] = job
            self._cancels[job_id] = cancel_event

        # If it is already on disk, finish immediately without a thread.
        if self._use_case.is_installed(model):
            done = job.succeeded(str(self._use_case.destination_path(model)))
            self._store(done)
            return done

        thread = threading.Thread(target=self._run, args=(job_id, ref, cancel_event), daemon=True)
        thread.start()
        return job

    def cancel(self, job_id: str) -> GgufDownloadJob | None:
        with self._lock:
            event = self._cancels.get(job_id)
            job = self._jobs.get(job_id)
        if event is not None:
            event.set()
        return job

    # -- internals ----------------------------------------------------------

    def _store(self, job: GgufDownloadJob) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def _run(self, job_id: str, ref: GgufModelRef, cancel_event: threading.Event) -> None:
        def on_progress(done: int, total: int | None) -> None:
            current = self.get(job_id)
            if current is not None:
                self._store(current.with_progress(done, total))

        try:
            path = self._use_case.execute(
                ref,
                progress_callback=on_progress,
                cancellation_check=cancel_event.is_set,
            )
            current = self.get(job_id)
            if current is not None:
                self._store(current.succeeded(path))
        except GgufDownloadCancelledError:
            current = self.get(job_id)
            if current is not None:
                self._store(current.cancelled())
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            current = self.get(job_id)
            if current is not None:
                self._store(current.failed(str(exc)))
