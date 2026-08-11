import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.domain.handbook_source import HANDBOOK_SOURCE_PATH


def content_hash(text: str) -> str:
    """Stable content fingerprint for a file, used to tell whether it changed
    since it was last indexed (incremental re-index). Independent of mtime."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# Paths that live in the index but not on disk. The handbook is indexed as a
# pseudo-document so "what is this project" retrieves it, which means the
# manifest legitimately holds a path no directory walk will ever return.
PSEUDO_DOCUMENT_PATHS = frozenset({HANDBOOK_SOURCE_PATH})


@dataclass(frozen=True)
class IndexDiff:
    """What an incremental re-index would touch: the one answer to "what changed".

    This existed twice, written slightly differently, and the two drifted — which
    is the whole reason it now lives here. The hint above the button counted a
    file as removed whenever it was in the manifest but not in the scan; the
    button itself, doing its own subtraction, knew to keep the handbook
    pseudo-document. So the hint read "1 file(s) changed" permanently, on a
    project where nothing had changed, directly above a button that answered
    "nothing changed" — and both were reporting honestly from their own private
    arithmetic. One function, two callers, no room to disagree.
    """

    changed: tuple[str, ...]
    new: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def pending(self) -> int:
        return len(self.changed) + len(self.new) + len(self.removed)


def diff_against_manifest(
    *,
    current_hashes: dict[str, str],
    manifest: dict[str, dict],
    pseudo_paths: Iterable[str] = PSEUDO_DOCUMENT_PATHS,
) -> IndexDiff:
    """Compare what is on disk now against what the index already holds.

    ``current_hashes`` is {path: content_hash} for the indexable files a fresh
    look at the project found. ``manifest`` is what was indexed last time.

    Pseudo-documents are excluded from "removed": they are in the index by
    design and were never on disk, so subtracting the two sets without
    accounting for them reports a deletion that never happened — every single
    time, for ever.
    """
    excluded = set(pseudo_paths)
    indexed = set(manifest) - excluded
    present = set(current_hashes)

    changed: list[str] = []
    new: list[str] = []
    unchanged: list[str] = []
    for path, digest in current_hashes.items():
        prior = manifest.get(path)
        if prior is None:
            new.append(path)
        elif str(prior.get("hash")) != digest:
            changed.append(path)
        else:
            unchanged.append(path)

    return IndexDiff(
        changed=tuple(sorted(changed)),
        new=tuple(sorted(new)),
        removed=tuple(sorted(indexed - present)),
        unchanged=tuple(sorted(unchanged)),
    )


@dataclass(frozen=True)
class TextChunk:
    id: str
    workspace_id: str
    source_path: str
    chunk_index: int
    content: str
    token_estimate: int
    metadata: dict[str, str]


@dataclass(frozen=True)
class SourceChunk:
    """One stored chunk of a file, in index order — used to expand a retrieved
    chunk with its neighbours (parent-document / small-to-big retrieval)."""

    chunk_index: int
    chunk_id: str
    content: str


@dataclass(frozen=True)
class IndexedDocumentSummary:
    source_path: str
    chunks_count: int


@dataclass(frozen=True)
class WorkspaceIndexResult:
    workspace_id: str
    indexed_files_count: int
    chunks_count: int
    skipped_files_count: int
    documents: list[IndexedDocumentSummary]
    # Abstention threshold calibrated to the embedding model (noise floor of random
    # chunk pairs); None when the index was too small to sample a trustworthy value.
    relevance_floor: float | None = None
    # Empirical chit-chat ceiling from neutral probe queries against this corpus;
    # None when there was nothing to embed or the provider can't be probed.
    relevance_probe_ceiling: float | None = None


@dataclass(frozen=True)
class IncrementalIndexResult:
    """Outcome of an incremental (changed-files-only) re-index."""

    workspace_id: str
    reindexed_files: int
    removed_files: int
    unchanged_files: int
    chunks_indexed: int
    indexed_files_count: int  # total in the index after the update
    chunks_count: int  # total in the index after the update
    documents: list[IndexedDocumentSummary]  # the files that were (re)indexed
    # Recalibrated abstention floor when enough chunks changed to resample; None when
    # too few changed (the caller keeps the previously-calibrated floor).
    relevance_floor: float | None = None
    # Recalibrated chit-chat ceiling from the changed chunks; None when nothing was
    # re-embedded (the caller keeps the previously-calibrated ceiling).
    relevance_probe_ceiling: float | None = None


@dataclass(frozen=True)
class IndexChangePreview:
    """A cheap, embed-free count of what an incremental re-index would touch,
    so the UI can show "N files changed since the last index" and decide whether
    to auto-update."""

    workspace_id: str
    has_index: bool
    changed_files: int
    new_files: int
    removed_files: int
    unchanged_files: int

    @property
    def pending(self) -> int:
        return self.changed_files + self.new_files + self.removed_files


@dataclass(frozen=True)
class ContextSearchResult:
    chunk_id: str
    source_path: str
    content: str
    score: float
    metadata: dict[str, str]
