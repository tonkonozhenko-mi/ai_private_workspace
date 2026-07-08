"""The project file walk must skip heavy vendored/VCS directories WITHOUT
descending into them (that walk of a whole monorepo/.git was the slow scan)."""

import tempfile
from pathlib import Path

from app.adapters.filesystem.local_file_system import LocalFileSystem


def _touch(root: Path, rel: str, text: str = "x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_scan_excludes_skipped_directories():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # Real project files.
        _touch(root, "main.py", "print()\n")
        _touch(root, "src/app.py", "x")
        _touch(root, "README.md", "# hi")
        # Heavy directories that must be pruned, not walked.
        _touch(root, ".git/objects/pack/huge", "junk")
        _touch(root, "node_modules/left-pad/index.js", "module.exports")
        _touch(root, ".venv/lib/site.py", "junk")
        _touch(root, "target/debug/app", "binary")

        result = LocalFileSystem().list_files(str(root))
        paths = {f.path for f in result}

        assert paths == {"main.py", "src/app.py", "README.md"}
        # Nothing from a skipped tree leaked in.
        assert not any(p.startswith((".git/", "node_modules/", ".venv/", "target/")) for p in paths)


def test_scan_does_not_descend_into_a_symlink_loop_in_a_skipped_dir():
    # If the walk descended into node_modules it could follow a self-referential
    # symlink and hang/raise. Pruning means it never enters, so this returns fast.
    import os

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, "main.py", "print()\n")
        (root / "node_modules").mkdir()
        try:
            os.symlink(str(root / "node_modules"), str(root / "node_modules" / "loop"))
        except (OSError, NotImplementedError):
            return  # platform without symlink support — skip
        result = LocalFileSystem().list_files(str(root))
        assert {f.path for f in result} == {"main.py"}


def test_scan_prunes_gitignored_directories_during_the_walk():
    # A large ignored tree must never be descended into: the .gitignore rule prunes
    # it at the directory level, so its files are not even discovered.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, ".gitignore", "big_data/\ncoverage/\n*.log\n")
        _touch(root, "main.py", "print()\n")
        _touch(root, "keep/a.py", "x")
        _touch(root, "run.log", "noise")  # file-level ignore, not a dir prune
        for i in range(50):
            _touch(root, f"big_data/f{i}.json", "{}")
            _touch(root, f"coverage/c{i}.html", "<html>")

        paths = {f.path for f in LocalFileSystem().list_files(str(root))}
        # Ignored directories are absent (never walked)…
        assert not any(p.startswith(("big_data/", "coverage/")) for p in paths), paths
        # …while real files and the .gitignore itself are discovered. run.log is a
        # file-level ignore that the scan use-case filter drops later, not here.
        assert {"main.py", "keep/a.py", ".gitignore", "run.log"} == paths, paths


def test_scan_honours_nested_gitignore_and_can_be_disabled():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, "keep/a.py", "x")
        _touch(root, "keep/.gitignore", "tmp/\n")
        for i in range(20):
            _touch(root, f"keep/tmp/t{i}.py", "x")

        pruned = {f.path for f in LocalFileSystem().list_files(str(root))}
        assert not any(p.startswith("keep/tmp/") for p in pruned), pruned

        # With gitignore disabled, the walk descends into everything again.
        full = {f.path for f in LocalFileSystem().list_files(str(root), respect_gitignore=False)}
        assert any(p.startswith("keep/tmp/") for p in full)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
