# -*- mode: python ; coding: utf-8 -*-
# PyInstaller proof-of-concept spec for AI Private Workspace backend.
# Build from the repository root through scripts/build_pyinstaller_backend_runtime.sh.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
BACKEND_DIR = SPEC_DIR.parent
ENTRYPOINT = BACKEND_DIR / "packaging" / "pyinstaller_backend_entrypoint.py"

hiddenimports = []
for package in [
    "app",
    "uvicorn",
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_core",
    "yaml",
    # Imported lazily (inside the PDF extractor) so PyInstaller's static analysis
    # cannot see it — name it here or PDFs silently stop working in the bundle.
    "pypdf",
]:
    hiddenimports.extend(collect_submodules(package))

datas = []
for package in ["app"]:
    datas.extend(collect_data_files(package, include_py_files=False))
block_cipher = None


a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir build: the executable stays small and the runtime is laid out in a
# folder next to it (_internal/). This avoids the onefile bootloader unpacking
# the whole runtime to a temp dir on every launch, which made cold starts slow.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ai-private-workspace-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ai-private-workspace-backend",
)
