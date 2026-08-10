#!/usr/bin/env python3
"""Raise pins in requirements.lock to meet the floors in requirements*.txt.

Dependabot bumps the FLOOR (``fastapi>=0.141.1``) but knows nothing about our
``requirements.lock`` — and the lock is what CI, the release build and the
desktop packaging actually install. So every Dependabot PR used to merge and
change nothing at all: the floor rose, the old version kept shipping. The guard
in tests/test_requirements_lock_matches_floors.py makes that visible; this
script is the one-command answer to it.

    python scripts/sync_requirements_lock.py            # show what would change
    python scripts/sync_requirements_lock.py --write    # apply

Scope, stated plainly: this moves the DIRECT pins only. It does not re-resolve
transitive dependencies, because that needs a real installer against PyPI. That
is usually fine for a floor bump, and it is not silent — CI installs the lock,
so a genuinely incompatible pin fails there with pip's own message. When a bump
is larger than a patch, or when pip complains, rebuild the lock properly:

    cd backend
    python -m venv .venv-lock && . .venv-lock/bin/activate
    pip install -r requirements.txt
    pip freeze --exclude-editable > requirements.lock
    # then restore the uvloop platform marker at the bottom of the file
"""

import argparse
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
LOCK = BACKEND / "requirements.lock"
REQUIREMENTS = (BACKEND / "requirements.txt", BACKEND / "requirements-qdrant.txt")

_FLOOR = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?>=([0-9][^,;\s]*)")
_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^;\s]+)")


def canonical(name: str) -> str:
    """PEP 503: '-' and '_' are the same, case does not matter."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:4])


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def declared_floors() -> dict[str, str]:
    floors: dict[str, str] = {}
    for path in REQUIREMENTS:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = strip_comment(raw)
            if not line or line.startswith("-"):
                continue
            match = _FLOOR.match(line)
            if match:
                floors[canonical(match.group(1))] = match.group(2)
    return floors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="apply the changes")
    args = parser.parse_args()

    floors = declared_floors()
    lines = LOCK.read_text(encoding="utf-8").splitlines(keepends=True)
    changes: list[str] = []
    out: list[str] = []

    for raw in lines:
        match = _PIN.match(strip_comment(raw))
        if match:
            name, pinned = canonical(match.group(1)), match.group(2)
            floor = floors.get(name)
            if floor and version_key(pinned) < version_key(floor):
                changes.append(f"{match.group(1)}: {pinned} -> {floor}")
                out.append(raw.replace(f"=={pinned}", f"=={floor}", 1))
                continue
        out.append(raw)

    if not changes:
        print("requirements.lock already meets every declared floor.")
        return 0

    print("\n".join(f"  {c}" for c in changes))
    if not args.write:
        print("\nNothing written. Re-run with --write to apply.")
        return 1

    LOCK.write_text("".join(out), encoding="utf-8")
    print(f"\nUpdated {LOCK.relative_to(BACKEND.parent)} ({len(changes)} pins).")
    print("CI installs this lock — watch that step for transitive conflicts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
