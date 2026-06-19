"""Read-only git history reader.

Runs a small set of read-only ``git`` queries against the project directory and
parses them into a :class:`GitInsights` snapshot. It never writes to the repo,
never runs hooks, and degrades to ``not_a_repo()`` whenever anything is missing
(git not installed, not a repository, command error, or timeout).
"""

import subprocess
from collections import Counter
from pathlib import Path

from app.core.domain.git_insights import (
    GitCommit,
    GitContributor,
    GitFileHotspot,
    GitInsights,
    infer_branch_strategy,
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

        return GitInsights(
            is_repo=True,
            branch=self._branch(root),
            last_commit=self._last_commit(root),
            total_commits=self._count(root, ["rev-list", "--count", "HEAD"]),
            commits_last_30_days=self._count(
                root, ["rev-list", "--count", "--since=30 days ago", "HEAD"]
            ),
            contributors_count=self._contributors_count(root),
            first_commit_at=self._first_commit_at(root),
            top_contributors=self._top_contributors(root),
            hotspots=self._hotspots(root),
            branch_strategy=self._branch_strategy(root),
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

    def _top_contributors(self, root: Path, limit: int = 4) -> list[GitContributor]:
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
            contributors.append(GitContributor(name=name.strip(), commits=count))
            if len(contributors) >= limit:
                break
        return contributors

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
