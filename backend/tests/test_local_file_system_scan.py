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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
