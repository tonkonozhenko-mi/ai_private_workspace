"""Stream a GGUF model file from a URL (e.g. Hugging Face) to local disk.

Safe-by-construction: the file is written to a ``.part`` temp path and only
atomically renamed into place once the full download completes, so a cancel,
crash, or network drop never leaves a truncated model that looks installed.

The ``.part`` file is also what makes a second attempt cheap. A 5 GB model over
a domestic connection is tens of minutes, and a network blip at minute forty
used to delete every byte and start again from zero — which, on a link that
drops regularly, is a download that can never finish no matter how many times
you press the button. Now the bytes stay and the next attempt asks the server to
continue from where they end.

Resuming needs one thing to be safe: knowing that the bytes on disk came from
the same file the server is serving now. Appending to a leftover from a
different revision would produce a model that is corrupt and looks installed.

The first version of this asked the *catalog* how big the file should be. That
was wrong, and wrong in a way that made the whole feature a no-op: the catalog
carries round approximations (``2_500_000_000``, and a comment saying so) while
the server reports the exact byte count. They never matched, so every resume
was refused, the partial file was deleted, and the download restarted from zero
with an error message about a file that had not changed at all. Every test
passed the true size, so every test agreed with the code and none of them with
reality.

The identity of a download is now what the server itself said the first time we
stored a byte of it, kept in a small sidecar next to the ``.part``. The catalog
size is advisory only — a fallback for the progress bar when a server sends no
length at all.
"""

from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.ports.gguf_downloader import (
    GgufDownloadCancelledError,
    GgufDownloadError,
)

_CHUNK_BYTES = 1024 * 1024  # 1 MiB


class _StartOver(Exception):
    """The stored bytes belong to a different file than the one being served."""


class HuggingFaceGgufDownloader:
    def __init__(self, timeout_seconds: int = 60, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    def download(
        self,
        url: str,
        destination_path: str,
        expected_size_bytes: int | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> str:
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        part_path = destination.with_suffix(destination.suffix + ".part")
        total_path = _sidecar_path(part_path)

        client = self._client or httpx.Client(follow_redirects=True)
        owns_client = self._client is None
        try:
            try:
                self._attempt(
                    client,
                    url,
                    part_path,
                    total_path,
                    expected_size_bytes,
                    progress_callback,
                    cancellation_check,
                )
            except _StartOver:
                # Nothing to salvage, and nothing to tell the person about: they
                # asked for the model, so fetch it whole rather than stopping to
                # explain that a file they never saw has been discarded.
                _discard(part_path, total_path)
                self._attempt(
                    client,
                    url,
                    part_path,
                    total_path,
                    expected_size_bytes,
                    progress_callback,
                    cancellation_check,
                )
        finally:
            if owns_client:
                client.close()

        # Atomic publish: only a fully-downloaded file ever appears at the path.
        part_path.replace(destination)
        _safe_unlink(total_path)
        return str(destination)

    def _attempt(
        self,
        client: httpx.Client,
        url: str,
        part_path: Path,
        total_path: Path,
        expected_size_bytes: int | None,
        progress_callback: Callable[[int, int | None], None] | None,
        cancellation_check: Callable[[], bool] | None,
    ) -> None:
        known_total = _recorded_total(total_path)
        resume_from = _resumable_bytes(part_path, known_total)
        headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
        downloaded = resume_from

        try:
            with client.stream("GET", url, timeout=self.timeout_seconds, headers=headers) as resp:
                if resp.status_code == 416:
                    # The range is past the end of the file being served, so the
                    # leftover is not part of it.
                    raise _StartOver
                if resp.status_code >= 400:
                    raise GgufDownloadError(
                        f"Download failed with HTTP {resp.status_code} for {url}"
                    )

                resuming = resp.status_code == 206 and resume_from > 0
                if resuming:
                    served_total = _total_bytes(resp, resuming=True)
                    if served_total is not None and served_total != known_total:
                        raise _StartOver
                if not resuming:
                    # Either there was nothing to resume, or the server ignored
                    # the Range header and is sending the whole file again. Both
                    # mean these bytes start at zero.
                    downloaded = 0
                total = _total_bytes(resp, resuming=resuming) or expected_size_bytes
                if not resuming and total is not None:
                    # Recorded before the first byte lands, so an interruption
                    # one chunk in still leaves something a resume can check.
                    _record_total(total_path, total)

                with open(part_path, "ab" if resuming else "wb") as handle:
                    for chunk in resp.iter_bytes(_CHUNK_BYTES):
                        if cancellation_check is not None and cancellation_check():
                            raise GgufDownloadCancelledError("Model download cancelled")
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)
        except GgufDownloadCancelledError:
            # Cancelling is a decision, not an interruption: the person does not
            # want this model, so the partial file goes with it.
            _discard(part_path, total_path)
            raise
        except (GgufDownloadError, _StartOver):
            raise
        except httpx.HTTPError as exc:
            # Keep the .part. This is the whole point — the next attempt resumes
            # from here instead of throwing away everything already transferred.
            raise GgufDownloadError(
                f"Network error downloading {url} after {downloaded} bytes: {exc}. "
                "The partly-downloaded file was kept; starting the download again "
                "will continue from where it stopped."
            ) from exc


def _sidecar_path(part_path: Path) -> Path:
    return part_path.with_suffix(part_path.suffix + ".total")


def _record_total(total_path: Path, total: int) -> None:
    try:
        total_path.write_text(str(total), encoding="utf-8")
    except OSError:
        # Losing the sidecar costs a restart, never correctness: without it
        # nothing is resumed.
        pass


def _recorded_total(total_path: Path) -> int | None:
    try:
        return int(total_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _resumable_bytes(part_path: Path, known_total: int | None) -> int:
    """How many bytes of ``part_path`` may safely be kept and continued from.

    Resuming needs the size the server gave when these bytes were stored. A
    ``.part`` with no sidecar is from a version that did not record one, or from
    a run that died before the first response — either way its provenance is
    unknown, so it is not appended to.
    """
    if known_total is None or known_total <= 0:
        return 0
    try:
        if not part_path.is_file():
            return 0
        existing = part_path.stat().st_size
    except OSError:
        return 0
    if existing <= 0 or existing >= known_total:
        return 0
    return existing


def _total_bytes(response: "httpx.Response", *, resuming: bool) -> int | None:
    """The size of the whole file, not of this response.

    On a resumed request Content-Length describes only the remaining tail, so
    reporting it as the total would show a progress bar that is wrong by exactly
    the part already on disk. Content-Range carries the real total.
    """
    if resuming:
        content_range = response.headers.get("content-range", "")
        _, _, total = content_range.partition("/")
        try:
            return int(total)
        except ValueError:
            return None
    raw = response.headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _discard(part_path: Path, total_path: Path) -> None:
    _safe_unlink(part_path)
    _safe_unlink(total_path)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
