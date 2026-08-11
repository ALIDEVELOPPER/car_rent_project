# -*- mode: python ; coding: utf-8 -*-
import os

PROJECT_ROOT = os.path.dirname(SPECPATH)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")

a = Analysis(
    [os.path.join(SPECPATH, "main.py")],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=[
        (FRONTEND_DIR, "frontend"),
        (MIGRATIONS_DIR, "migrations"),
    ],
    hiddenimports=[
        "logging.config",
        "webview.platforms.qt",
        "webview.platforms.gtk",
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtWebChannel",
        "PyQt5.QtPrintSupport",
        "alembic",
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AgenceLocation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AgenceLocation",
)
