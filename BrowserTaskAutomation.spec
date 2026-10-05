# -*- mode: python ; coding: utf-8 -*-
"""Package the control panel as one Windows executable.

The Playwright driver is included so the exe can launch the installed Chrome.
Chrome itself is not bundled.
"""

from pathlib import Path

import playwright
from PyInstaller.utils.hooks import collect_data_files, collect_submodules


driver = Path(playwright.__file__).resolve().parent / "driver"

hiddenimports = collect_submodules("playwright") + collect_submodules("app") + [
    "playwright.sync_api",
    "greenlet",
    "sqlalchemy.dialects.sqlite",
    "cryptography.fernet",
]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[(str(driver), "playwright/driver")] + collect_data_files("playwright"),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BrowserTaskAutomation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
