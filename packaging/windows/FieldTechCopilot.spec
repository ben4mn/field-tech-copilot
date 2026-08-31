# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from pathlib import Path


repo_root = Path(SPECPATH).parents[1]
hidden_imports = collect_submodules("uvicorn")

analysis = Analysis(
    [str(repo_root / "src" / "fieldtech" / "desktop.py")],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=[
        (str(repo_root / "src" / "fieldtech" / "api" / "static"), "fieldtech/api/static"),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="FieldTechCopilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

diagnostics = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="FieldTechCopilotDiagnostics",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    executable,
    diagnostics,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FieldTechCopilot",
)
