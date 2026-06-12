# -*- mode: python ; coding: utf-8 -*-
# PyInstaller proof-of-concept spec for AI Private Workspace backend.
# Build from the repository root through scripts/build_pyinstaller_backend_runtime.sh.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
BACKEND_DIR = SPEC_DIR.parent
ENTRYPOINT = BACKEND_DIR / "packaging" / "pyinstaller_backend_entrypoint.py"

hiddenimports = collect_submodules("app")
block_cipher = None


a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=[],
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
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
