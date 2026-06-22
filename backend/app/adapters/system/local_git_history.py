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

from app.core.domain.git_insights import (
    GitActivitySummary,
    GitCommit,
    GitContributor,
    GitFileActivity,
    GitFileHotspot,
    GitInsights,
    infer_branch_strategy,
    summarize_activity,
)

_UNIT = "\x1f"  # ASCII unit separator — safe field delimiter for git --pretty.


class LocalGitHistory:
    def __init__(self, timeout_seconds: int = 8, hotspot_window_days: int = 90) -> None:
        self.timeout_seconds = timeout_seconds
        self.hotspot_window_days = hotspot_window_days

    def read_insights(self, project_path: str) -> GitInsights:
        root = Path(project_path).expanduser()
        if not root.exists() or not root.is_dir():
            return GitInsights.not_a_repo()

        inside = self._run(root, ["rev-parse", "--is-inside-work-tree"])
        if inside is None or inside.strip() != "true":
            return GitInsights.not_a_repo()

        total_commits = self._count(root, ["rev-list", "--count", "HEAD"])
        window = self._activity_window(root)
        summary = summarize_activity(window, datetime.now(timezone.utc))

        commits_90 = self._count(
            root, ["rev-list", "--count", "--since=90 days ago", "HEAD"]
        )
        commits_90_no_merges = self._count(
            root, ["rev-list", "--count", "--since=90 days ago", "--no-merges", "HEAD"]
        )
        merge_share = (
            (commits_90 - commits_90_no_merges) / commits_90 if commits_90 > 0 else 0.0
        )

        return GitInsights(
            is_repo=True,
            branch=self._branch(root),
            last_commit=self._last_commit(root),
            total_commits=total_commits,
            commits_last_30_days=self._count(
                root, ["rev-list", "--count", "--since=30 days ago", "HEAD"]
            ),
            contributors_count=self._contributors_count(root),
            first_commit_at=self._first_commit_at(root),
            top_contributors=self._top_contributors(root, total_commits, summary),
            hotspots=self._hotspots(root),
            branch_strategy=self._branch_strategy(root),
            commits_last_7_days=self._count(
                root, ["rev-list", "--count", "--since=7 days ago", "HEAD"]
            ),
            commits_last_90_days=commits_90,
            active_contributors_90d=summary.active_contributors,
            merge_commit_share=round(merge_share, 3),
            recent_commits=self._recent_commits(root),
            activity_weeks=summary.weeks,
            activity_by_weekday=summary.by_weekday,
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

        pathspec = ["--", relative_path] if relative_path else []

        total = self._count(root, ["rev-list", "--count", "HEAD", *pathspec])

        # Top authors of this path (or the repo), counted from the log.
        authors_raw = self._run(
            root, ["log", "--no-merges", "--pretty=format:%an", *pathspec]
        )
        counter: Counter[str] = Counter()
        if authors_raw:
            for line in authors_raw.splitlines():
                name = line.strip()
                if name:
                    counter[name] += 1
        top_authors = [
            GitContributor(name=name, commits=count)
            for name, count in counter.most_common(5)
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

    def _last_commit(self, root: Path) -> GitCommit | None:
        pretty = _UNIT.join(["%h", "%s", "%an", "%cI"])
        value = self._run(root, ["log", "-1", f"--pretty=format:{pretty}"])
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

    def _contributors_count(self, root: Path) -> int:
        value = self._run(root, ["shortlog", "-sn", "--all", "--no-merges"])
        if not value:
            return 0
        return len([line for line in value.splitlines() if line.strip()])

    def _first_commit_at(self, root: Path) -> str | None:
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
    ) -> list[GitContributor]:
        value = self._run(root, ["shortlog", "-sn", "--all", "--no-merges"])
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

    def _activity_window(self, root: Path) -> list[tuple[datetime, str]]:
        """Authored commits (no merges) in the last 90 days as (datetime, author)."""
        value = self._run(
            root,
            [
                "log",
                "--since=90 days ago",
                "--no-merges",
                f"--pretty=format:%cI{_UNIT}%an",
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

    def _recent_commits(self, root: Path, limit: int = 10) -> list[GitCommit]:
        pretty = _UNIT.join(["%h", "%s", "%an", "%cI"])
        value = self._run(
            root, ["log", f"-{limit}", "--no-merges", f"--pretty=format:{pretty}"]
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

    def _hotspots(self, root: Path, limit: int = 6) -> list[GitFileHotspot]:
        value = self._run(
            root,
            [
                "log",
                f"--since={self.hotspot_window_days} days ago",
                "--name-only",
                "--pretty=format:",
                "--no-merges",
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
