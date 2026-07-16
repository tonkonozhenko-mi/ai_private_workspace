"""Read-only git history reader.

Runs a small set of read-only ``git`` queries against the project directory and
parses them into a :class:`GitInsights` snapshot. It never writes to the repo,
never runs hooks, and degrades to ``not_a_repo()`` whenever anything is missing
(git not installed, not a repository, command error, or timeout).
"""

import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.domain.git_insights import (
    GitActivitySummary,
    GitCommit,
    GitContributor,
    GitFileActivity,
    GitFileHotspot,
    GitInsights,
    compute_couplings,
    infer_branch_strategy,
    summarize_activity,
    summarize_merges,
)

if TYPE_CHECKING:
    # Annotation-only; the runtime import lives inside change_brief() where the
    # value is actually constructed.
    from app.core.domain.git_change_brief import GitChangeBrief

_UNIT = "\x1f"  # ASCII unit separator — safe field delimiter for git --pretty.


class LocalGitHistory:
    def __init__(
        self,
        timeout_seconds: int = 8,
        hotspot_window_days: int = 90,
        coupling_window_days: int = 180,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.hotspot_window_days = hotspot_window_days
        self.coupling_window_days = coupling_window_days

    def read_insights(self, project_path: str) -> GitInsights:
        root = Path(project_path).expanduser()
        if not root.exists() or not root.is_dir():
            return GitInsights.not_a_repo()

        # These two are different answers and were the same one. `_run` returns
        # None when git could not be asked — a timeout, a missing binary, a
        # folder macOS has not granted us yet — and that is "unknown". Only git
        # itself saying something other than "true" means "not a repository".
        inside = self._run(root, ["rev-parse", "--is-inside-work-tree"])
        if inside is None:
            return GitInsights.unknown()
        if inside.strip() != "true":
            return GitInsights.not_a_repo()

        # If this workspace is a subfolder of a bigger repo, limit every query to
        # its own path so we never report the parent repository's history.
        scope = self._scope(root)

        total_commits = self._count(root, ["rev-list", "--count", "HEAD", *scope])
        window = self._activity_window(root, scope)
        summary = summarize_activity(window, datetime.now(timezone.utc))

        commits_90 = self._count(
            root, ["rev-list", "--count", "--since=90 days ago", "HEAD", *scope]
        )
        commits_90_no_merges = self._count(
            root, ["rev-list", "--count", "--since=90 days ago", "--no-merges", "HEAD", *scope]
        )
        merge_share = (commits_90 - commits_90_no_merges) / commits_90 if commits_90 > 0 else 0.0

        return GitInsights(
            is_repo=True,
            branch=self._branch(root),
            last_commit=self._last_commit(root, scope),
            total_commits=total_commits,
            commits_last_30_days=self._count(
                root, ["rev-list", "--count", "--since=30 days ago", "HEAD", *scope]
            ),
            contributors_count=self._contributors_count(root, scope),
            first_commit_at=self._first_commit_at(root, scope),
            top_contributors=self._top_contributors(root, total_commits, summary, scope=scope),
            hotspots=self._hotspots(root, scope=scope),
            branch_strategy=self._branch_strategy(root),
            commits_last_7_days=self._count(
                root, ["rev-list", "--count", "--since=7 days ago", "HEAD", *scope]
            ),
            commits_last_90_days=commits_90,
            active_contributors_90d=summary.active_contributors,
            merge_commit_share=round(merge_share, 3),
            recent_commits=self._recent_commits(root, scope=scope),
            activity_weeks=summary.weeks,
            activity_by_weekday=summary.by_weekday,
            merge_activity=self._merge_activity(root, scope),
            file_couplings=self._file_couplings(root, scope),
        )

    def change_brief(self, project_path: str, since_commit: str | None) -> "GitChangeBrief":
        """What landed in the repo since ``since_commit`` (the HEAD at the last
        watch check): commit count, authors, and changed files. Read-only.

        ``comparable`` is False when this is not a git repo, or when there is no
        usable baseline (first check, or the old commit is gone after a rebase/
        force-push) — the caller then shows no git brief rather than a wrong one.
        """
        from app.core.domain.git_change_brief import GitChangeBrief

        root = Path(project_path).expanduser()
        none = GitChangeBrief(comparable=False, head=None, commit_count=0)
        if not root.exists() or not root.is_dir():
            return none
        inside = self._run(root, ["rev-parse", "--is-inside-work-tree"])
        if inside is None or inside.strip() != "true":
            return none

        head = self._run(root, ["rev-parse", "HEAD"])
        head = head.strip() if head else None
        if head is None:
            return none
        if not since_commit:
            # First check: record the baseline, nothing to compare yet.
            return GitChangeBrief(comparable=False, head=head, commit_count=0)

        verified = self._run(
            root, ["rev-parse", "--verify", "--quiet", f"{since_commit}^{{commit}}"]
        )
        if not verified:
            # Baseline commit no longer in history (rebase/force-push) — can't diff.
            return GitChangeBrief(comparable=False, head=head, commit_count=0)
        if since_commit.strip() == head:
            return GitChangeBrief(comparable=True, head=head, commit_count=0)

        # Scope to the workspace path when it's a subfolder of a bigger repo, so
        # "what changed" reflects the workspace, not the parent repository.
        scope = self._scope(root)
        rng = f"{since_commit}..HEAD"
        count = self._count(root, ["rev-list", "--count", rng, *scope])
        authors_raw = self._run(root, ["log", "--format=%an", rng, *scope]) or ""
        authors: list[str] = []
        for name in authors_raw.splitlines():
            name = name.strip()
            if name and name not in authors:
                authors.append(name)
        changed_raw = self._run(root, ["diff", "--name-only", since_commit, "HEAD", *scope]) or ""
        changed = [line.strip() for line in changed_raw.splitlines() if line.strip()][:500]
        # Commit subjects (newest first), no merges — raw material for the
        # optional LLM "in short" summary. Capped so the log stays bounded.
        subjects_raw = self._run(root, ["log", "--no-merges", "--format=%s", rng, *scope]) or ""
        subjects = [line.strip() for line in subjects_raw.splitlines() if line.strip()][:200]
        return GitChangeBrief(
            comparable=True,
            head=head,
            commit_count=count,
            authors=authors,
            changed_paths=changed,
            commit_subjects=subjects,
        )

    def file_activity(
        self, project_path: str, relative_path: str | None = None
    ) -> GitFileActivity | None:
        root = Path(project_path).expanduser()
        if not root.exists() or not root.is_dir():
            return None
        inside = self._run(root, ["rev-parse", "--is-inside-work-tree"])
        if inside is None or inside.strip() != "true":
            return None

        # A specific file scopes to that file; otherwise fall back to the workspace
        # path so a repo-wide query on a nested workspace doesn't leak the parent
        # repository's history.
        pathspec = ["--", relative_path] if relative_path else self._scope(root)

        total = self._count(root, ["rev-list", "--count", "HEAD", *pathspec])

        # Top authors of this path (or the repo), counted from the log.
        authors_raw = self._run(root, ["log", "--no-merges", "--pretty=format:%an", *pathspec])
        counter: Counter[str] = Counter()
        if authors_raw:
            for line in authors_raw.splitlines():
                name = line.strip()
                if name:
                    counter[name] += 1
        top_authors = [
            GitContributor(name=name, commits=count) for name, count in counter.most_common(5)
        ]

        # Recent commits touching this path (or the repo).
        pretty = _UNIT.join(["%h", "%s", "%an", "%cI"])
        log_raw = self._run(
            root, ["log", "-8", "--no-merges", f"--pretty=format:{pretty}", *pathspec]
        )
        recent: list[GitCommit] = []
        if log_raw:
            for line in log_raw.splitlines():
                parts = line.split(_UNIT)
                if len(parts) < 4:
                    continue
                recent.append(
                    GitCommit(
                        short_hash=parts[0].strip(),
                        subject=parts[1].strip(),
                        author=parts[2].strip(),
                        committed_at=parts[3].strip(),
                    )
                )

        return GitFileActivity(
            path=relative_path,
            total_commits=total,
            top_authors=top_authors,
            recent_commits=recent,
        )

    # -- individual queries -------------------------------------------------

    def _branch(self, root: Path) -> str | None:
        value = self._run(root, ["rev-parse", "--abbrev-ref", "HEAD"])
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _branch_strategy(self, root: Path):
        """List local + remote branch names and infer the branching model.

        Remote-tracking names are normalised (``origin/feature/x`` →
        ``feature/x``) and ``origin/HEAD`` is dropped. Read-only.
        """
        value = self._run(
            root,
            [
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/heads",
                "refs/remotes",
            ],
        )
        if value is None:
            return None
        branches: set[str] = set()
        for line in value.splitlines():
            name = line.strip()
            if not name or name.endswith("/HEAD"):
                continue
            # Drop the remote name from remote-tracking refs (e.g. "origin/").
            if "/" in name and name.split("/", 1)[0] in {"origin", "upstream"}:
                name = name.split("/", 1)[1]
            if name:
                branches.add(name)
        if not branches:
            return None
        return infer_branch_strategy(sorted(branches), self._default_branch(root))

    def _default_branch(self, root: Path) -> str | None:
        value = self._run(root, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
        if value:
            name = value.strip()
            if "/" in name and name.split("/", 1)[0] in {"origin", "upstream"}:
                name = name.split("/", 1)[1]
            if name:
                return name
        return self._branch(root)

    def _last_commit(self, root: Path, scope: list[str] | None = None) -> GitCommit | None:
        pretty = _UNIT.join(["%h", "%s", "%an", "%cI"])
        value = self._run(root, ["log", "-1", f"--pretty=format:{pretty}", *(scope or [])])
        if not value:
            return None
        parts = value.split(_UNIT)
        if len(parts) < 4:
            return None
        return GitCommit(
            short_hash=parts[0].strip(),
            subject=parts[1].strip(),
            author=parts[2].strip(),
            committed_at=parts[3].strip(),
        )

    def _count(self, root: Path, args: list[str]) -> int:
        value = self._run(root, args)
        if value is None:
            return 0
        try:
            return int(value.strip())
        except ValueError:
            return 0

    def _contributors_count(self, root: Path, scope: list[str] | None = None) -> int:
        # ``--all`` would count every ref regardless of path; when scoped to a
        # subfolder we drop it and count contributors to that path's HEAD history.
        args = (
            ["shortlog", "-sn", "--no-merges", "HEAD"]
            if scope
            else ["shortlog", "-sn", "--all", "--no-merges"]
        )
        value = self._run(root, [*args, *(scope or [])])
        if not value:
            return 0
        return len([line for line in value.splitlines() if line.strip()])

    def _first_commit_at(self, root: Path, scope: list[str] | None = None) -> str | None:
        if scope:
            # The root-commit trick doesn't compose with a pathspec; take the
            # earliest commit that touched this path (oldest is the last line).
            value = self._run(root, ["log", "--pretty=format:%cI", *scope])
            if not value:
                return None
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            return lines[-1] if lines else None
        value = self._run(root, ["log", "--max-parents=0", "--pretty=format:%cI", "-1"])
        if not value:
            return None
        first_line = value.splitlines()[0].strip() if value.strip() else ""
        return first_line or None

    def _top_contributors(
        self,
        root: Path,
        total_commits: int,
        summary: GitActivitySummary,
        limit: int = 6,
        scope: list[str] | None = None,
    ) -> list[GitContributor]:
        args = (
            ["shortlog", "-sn", "--no-merges", "HEAD", *scope]
            if scope
            else ["shortlog", "-sn", "--all", "--no-merges"]
        )
        value = self._run(root, args)
        if not value:
            return []
        contributors: list[GitContributor] = []
        for line in value.splitlines():
            line = line.strip()
            if not line:
                continue
            count_str, _, name = line.partition("\t")
            if not name:
                # Fallback when partition is whitespace-separated.
                pieces = line.split(None, 1)
                if len(pieces) != 2:
                    continue
                count_str, name = pieces
            try:
                count = int(count_str.strip())
            except ValueError:
                continue
            clean = name.strip()
            contributors.append(
                GitContributor(
                    name=clean,
                    commits=count,
                    share=round(count / total_commits, 3) if total_commits > 0 else 0.0,
                    commits_last_90_days=summary.author_commits_90d.get(clean, 0),
                    last_active=summary.author_last_active.get(clean),
                )
            )
            if len(contributors) >= limit:
                break
        return contributors

    def _merge_activity(self, root: Path, scope: list[str] | None = None):
        """Approximate PR/MR activity from merge-commit subjects + (#N)/!N refs."""
        s = scope or []
        merges_raw = self._run(root, ["log", "--merges", "-500", "--pretty=format:%s", *s])
        all_raw = self._run(root, ["log", "-1000", "--pretty=format:%s", *s])
        if merges_raw is None and all_raw is None:
            return None
        merge_subjects = [s.strip() for s in (merges_raw or "").splitlines() if s.strip()]
        all_subjects = [s.strip() for s in (all_raw or "").splitlines() if s.strip()]
        return summarize_merges(merge_subjects, all_subjects)

    def _activity_window(
        self, root: Path, scope: list[str] | None = None
    ) -> list[tuple[datetime, str]]:
        """Authored commits (no merges) in the last 90 days as (datetime, author)."""
        value = self._run(
            root,
            [
                "log",
                "--since=90 days ago",
                "--no-merges",
                f"--pretty=format:%cI{_UNIT}%an",
                *(scope or []),
            ],
        )
        if not value:
            return []
        entries: list[tuple[datetime, str]] = []
        for line in value.splitlines():
            iso, _, author = line.partition(_UNIT)
            parsed = self._parse_iso(iso.strip())
            if parsed is not None and author.strip():
                entries.append((parsed, author.strip()))
        return entries

    def _recent_commits(
        self, root: Path, limit: int = 10, scope: list[str] | None = None
    ) -> list[GitCommit]:
        pretty = _UNIT.join(["%h", "%s", "%an", "%cI"])
        value = self._run(
            root, ["log", f"-{limit}", "--no-merges", f"--pretty=format:{pretty}", *(scope or [])]
        )
        if not value:
            return []
        commits: list[GitCommit] = []
        for line in value.splitlines():
            parts = line.split(_UNIT)
            if len(parts) < 4:
                continue
            commits.append(
                GitCommit(
                    short_hash=parts[0].strip(),
                    subject=parts[1].strip(),
                    author=parts[2].strip(),
                    committed_at=parts[3].strip(),
                )
            )
        return commits

    @staticmethod
    def _parse_iso(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _hotspots(
        self, root: Path, limit: int = 6, scope: list[str] | None = None
    ) -> list[GitFileHotspot]:
        value = self._run(
            root,
            [
                "log",
                f"--since={self.hotspot_window_days} days ago",
                "--name-only",
                "--pretty=format:",
                "--no-merges",
                *(scope or []),
            ],
        )
        if not value:
            return []
        counter: Counter[str] = Counter()
        for line in value.splitlines():
            path = line.strip()
            if path:
                counter[path] += 1
        return [
            GitFileHotspot(path=path, changes=changes)
            for path, changes in counter.most_common(limit)
        ]

    def _file_couplings(self, root: Path, scope: list[str] | None = None):
        """Per-commit file lists over the coupling window → temporal coupling.

        A unit-separator sentinel marks each commit boundary so file lists are
        grouped per commit regardless of filenames.
        """
        raw = self._run(
            root,
            [
                "log",
                f"--since={self.coupling_window_days} days ago",
                "--no-merges",
                "--name-only",
                f"--pretty=format:{_UNIT}C",
                *(scope or []),
            ],
        )
        if not raw:
            return []
        commits: list[list[str]] = []
        current: list[str] | None = None
        for line in raw.splitlines():
            if line.startswith(_UNIT + "C"):
                if current is not None:
                    commits.append(current)
                current = []
            elif line.strip():
                if current is None:
                    current = []
                current.append(line.strip())
        if current is not None:
            commits.append(current)
        return compute_couplings(commits)

    # -- scoping ------------------------------------------------------------

    def _scope(self, root: Path) -> list[str]:
        """A git pathspec that limits history to THIS workspace when it sits inside
        a larger repository, else an empty list.

        A workspace opened on a subfolder of a monorepo is still "inside a work
        tree" — git climbs to the parent ``.git`` — so unscoped ``git log`` /
        ``shortlog`` would report the *parent* repo's commits, contributors and
        messages. That is a privacy leak (another project's history bleeding into
        answers and stats). When the workspace root differs from the repo top level,
        we return ``["--", "<subpath>"]`` so every query counts only commits that
        touched files under the workspace. When the workspace *is* the repo root
        (the common case) this is empty and behaviour is unchanged."""
        top = self._run(root, ["rev-parse", "--show-toplevel"])
        if not top or not top.strip():
            return []
        try:
            top_path = Path(top.strip()).resolve()
            here = root.resolve()
        except OSError:
            return []
        if here == top_path:
            return []
        # Confirm the workspace really is *under* the repo top level (not a sibling
        # via symlinks); if so, scope to it. Every git command runs with ``-C
        # <workspace>``, so the pathspec is relative to the workspace — "." means
        # "this directory and below", i.e. exactly the workspace subtree.
        try:
            here.relative_to(top_path)
        except ValueError:
            return []
        return ["--", "."]

    # -- subprocess plumbing ------------------------------------------------

    def _run(self, root: Path, args: list[str]) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout
