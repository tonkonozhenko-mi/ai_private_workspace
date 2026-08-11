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
"""

from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.ports.gguf_downloader import (
    GgufDownloadCancelledError,
    GgufDownloadError,
)

_CHUNK_BYTES = 1024 * 1024  # 1 MiB


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

        resume_from = _resumable_bytes(part_path, expected_size_bytes)
        headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}

        client = self._client or httpx.Client(follow_redirects=True)
        owns_client = self._client is None
        downloaded = resume_from
        try:
            with client.stream("GET", url, timeout=self.timeout_seconds, headers=headers) as resp:
                if resp.status_code == 416:
                    # The server says the range is past the end of the file. The
                    # leftover is not part of this file — start over rather than
                    # publish bytes we cannot account for.
                    _safe_unlink(part_path)
                    raise GgufDownloadError(
                        f"The partly-downloaded file no longer matches {url}. "
                        "It has been discarded; starting the download again will fetch "
                        "the model from the beginning."
                    )
                if resp.status_code >= 400:
                    raise GgufDownloadError(
                        f"Download failed with HTTP {resp.status_code} for {url}"
                    )

                resuming = resp.status_code == 206 and resume_from > 0
                if resuming:
                    served_total = _total_bytes(resp, resuming=True)
                    if served_total is not None and served_total != expected_size_bytes:
                        # The file on the server is not the file these bytes came
                        # from. Appending would produce a corrupt model that
                        # passes every check the app makes, so refuse instead.
                        _safe_unlink(part_path)
                        raise GgufDownloadError(
                            f"{url} is now {served_total} bytes, not the "
                            f"{expected_size_bytes} the partly-downloaded file belongs to. "
                            "It has been discarded; start the download again."
                        )
                if not resuming:
                    # Either there was nothing to resume, or the server ignored
                    # the Range header and is sending the whole file again. Both
                    # mean these bytes start at zero.
                    downloaded = 0
                total = _total_bytes(resp, resuming=resuming) or expected_size_bytes

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
            _safe_unlink(part_path)
            raise
        except GgufDownloadError:
            raise
        except httpx.HTTPError as exc:
            # Keep the .part. This is the whole point — the next attempt resumes
            # from here instead of throwing away everything already transferred.
            raise GgufDownloadError(
                f"Network error downloading {url} after {downloaded} bytes: {exc}. "
                "The partly-downloaded file was kept; starting the download again "
                "will continue from where it stopped."
            ) from exc
        finally:
            if owns_client:
                client.close()

        # Atomic publish: only a fully-downloaded file ever appears at the path.
        part_path.replace(destination)
        return str(destination)


def _resumable_bytes(part_path: Path, expected_size_bytes: int | None) -> int:
    """How many bytes of ``part_path`` may safely be kept and continued from.

    Resuming only makes sense when we know how big the finished file should be:
    a leftover ``.part`` from a different revision of the same filename would
    otherwise be appended to and published as a valid-looking model that is
    quietly corrupt. Without an expected size, or with a leftover at least as
    large as one, the old bytes are not trusted and the download restarts.
    """
    if expected_size_bytes is None or expected_size_bytes <= 0:
        return 0
    try:
        if not part_path.is_file():
            return 0
        existing = part_path.stat().st_size
    except OSError:
        return 0
    if existing <= 0 or existing >= expected_size_bytes:
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


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
