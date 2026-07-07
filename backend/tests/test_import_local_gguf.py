"""Importing a GGUF the user already has: validation + registering it in the
managed model dir (symlink, copy fallback), without touching the original."""

import tempfile
from contextlib import contextmanager
from pathlib import Path

from app.core.domain.local_gguf_import import (
    GGUF_MAGIC,
    guess_gguf_model_type,
    imported_model_id,
    imported_relative_path,
)
from app.core.use_cases.import_local_gguf import (
    ImportLocalGgufUseCase,
    LocalGgufImportError,
)


@contextmanager
def raises(match: str):
    """Assert a LocalGgufImportError whose message contains ``match`` — a tiny
    stand-in so the file runs under the manual harness and pytest alike."""
    try:
        yield
    except LocalGgufImportError as exc:
        assert match in str(exc), f"expected {match!r} in {str(exc)!r}"
        return
    raise AssertionError(f"expected LocalGgufImportError containing {match!r}")


def _write_gguf(path: Path, *, size: int = 2_000_000, magic: bytes = GGUF_MAGIC) -> Path:
    path.write_bytes(magic + b"\x00" * (size - len(magic)))
    return path


# --- pure helpers ---------------------------------------------------------


def test_model_id_and_path_follow_the_custom_repo_convention():
    assert imported_model_id("My-Model-Q4.gguf") == "local/My-Model-Q4.gguf"
    assert imported_relative_path("My-Model-Q4.gguf") == "models/gguf/local/My-Model-Q4.gguf"


def test_embedding_models_are_detected_by_name():
    assert guess_gguf_model_type("nomic-embed-text.gguf") == "embedding"
    assert guess_gguf_model_type("bge-m3-Q4.gguf") == "embedding"
    assert guess_gguf_model_type("Qwen3-4B-Q4_K_M.gguf") == "llm"


# --- validation -----------------------------------------------------------


def test_missing_file_is_rejected():
    with tempfile.TemporaryDirectory() as d:
        uc = ImportLocalGgufUseCase(app_data_dir=d)
        with raises("No file"):
            uc.execute(str(Path(d) / "nope.gguf"))


def test_non_gguf_extension_is_rejected():
    with tempfile.TemporaryDirectory() as d:
        src = _write_gguf(Path(d) / "model.bin")
        uc = ImportLocalGgufUseCase(app_data_dir=str(Path(d) / "app"))
        with raises("not a .gguf"):
            uc.execute(str(src))


def test_tiny_file_is_rejected_as_incomplete():
    with tempfile.TemporaryDirectory() as d:
        src = _write_gguf(Path(d) / "model.gguf", size=100)
        uc = ImportLocalGgufUseCase(app_data_dir=str(Path(d) / "app"))
        with raises("too small"):
            uc.execute(str(src))


def test_wrong_magic_is_rejected():
    with tempfile.TemporaryDirectory() as d:
        src = _write_gguf(Path(d) / "model.gguf", magic=b"ZZZZ")
        uc = ImportLocalGgufUseCase(app_data_dir=str(Path(d) / "app"))
        with raises("GGUF"):
            uc.execute(str(src))


# --- happy path -----------------------------------------------------------


def test_import_registers_the_model_via_symlink_without_copying():
    with tempfile.TemporaryDirectory() as d:
        src = _write_gguf(Path(d) / "Qwen3-4B-Q4_K_M.gguf")
        app_dir = Path(d) / "app"
        result = ImportLocalGgufUseCase(app_data_dir=str(app_dir)).execute(str(src))

        assert result.model_id == "local/Qwen3-4B-Q4_K_M.gguf"
        assert result.model_type == "llm"
        assert result.size_bytes == 2_000_000
        stored = Path(result.stored_path)
        assert stored.exists()
        # A symlink was used (no large copy) and it points back at the original.
        assert result.linked is True
        assert stored.is_symlink()
        assert stored.resolve() == src.resolve()


def test_reimport_is_idempotent():
    with tempfile.TemporaryDirectory() as d:
        src = _write_gguf(Path(d) / "model.gguf")
        app_dir = Path(d) / "app"
        uc = ImportLocalGgufUseCase(app_data_dir=str(app_dir))
        first = uc.execute(str(src))
        second = uc.execute(str(src))
        assert first.stored_path == second.stored_path
        assert Path(second.stored_path).resolve() == src.resolve()


def test_explicit_model_type_overrides_the_guess():
    with tempfile.TemporaryDirectory() as d:
        src = _write_gguf(Path(d) / "mystery.gguf")
        uc = ImportLocalGgufUseCase(app_data_dir=str(Path(d) / "app"))
        result = uc.execute(str(src), model_type="embedding")
        assert result.model_type == "embedding"


if __name__ == "__main__":
    import traceback

    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                passed += 1
                print("PASS", name)
            except BaseException:  # noqa: BLE001
                failed += 1
                print("FAIL", name)
                traceback.print_exc()
    print(f"--- {passed} passed, {failed} failed ---")
