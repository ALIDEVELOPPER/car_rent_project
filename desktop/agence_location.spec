# -*- mode: python ; coding: utf-8 -*-
import os
import sys

PROJECT_ROOT = os.path.dirname(SPECPATH)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
MIGRATIONS_DIR = os.path.join(BACKEND_DIR, "migrations")
# Polices arabes (Amiri) embarquées pour les PDF en arabe
ASSETS_DIR = os.path.join(BACKEND_DIR, "app", "assets")

# pyinstaller s'exécute nativement sur chaque OS cible (impossible de cross-compiler),
# donc sys.platform ici reflète toujours le bon système : ce .spec unique sert pour
# les trois builds (Linux, Windows, Mac) sans modification.
hiddenimports = [
    "logging.config",
    "alembic",
    "sqlalchemy.dialects.sqlite",
    # Mise en forme du texte arabe pour les PDF
    "arabic_reshaper",
    "bidi",
    "bidi.algorithm",
    "openpyxl",
    "pyzipper",
]

if sys.platform.startswith("linux"):
    # requirements.txt installe pywebview[qt5] uniquement sur Linux
    hiddenimports += [
        "webview.platforms.qt",
        "webview.platforms.gtk",
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtWebChannel",
        "PyQt5.QtPrintSupport",
    ]
elif sys.platform == "win32":
    hiddenimports += ["webview.platforms.edgechromium", "webview.platforms.winforms"]
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]

a = Analysis(
    [os.path.join(SPECPATH, "main.py")],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=[
        (FRONTEND_DIR, "frontend"),
        (MIGRATIONS_DIR, "migrations"),
        (ASSETS_DIR, os.path.join("app", "assets")),
    ],
    hiddenimports=hiddenimports,
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
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(FRONTEND_DIR, "assets", "logo", "icon.ico"),
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

# Sans ce bloc, macOS produit juste un dossier + un binaire brut lançable en
# terminal, pas une vraie app double-cliquable depuis le Finder.
if sys.platform == "darwin":
    # PyInstaller exige un .icns pour BUNDLE (pas le .png/.ico utilisé sur les
    # autres OS) ; à générer depuis frontend/assets/logo/icon.png sur un Mac
    # (iconutil ou équivalent) quand on aura une machine pour le tester.
    app = BUNDLE(
        coll,
        name="AgenceLocation.app",
        icon=None,
        bundle_identifier="com.agencelocation.desktop",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSBackgroundOnly": False,
        },
    )
