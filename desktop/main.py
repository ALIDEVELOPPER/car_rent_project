import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Le plugin Qt5 natif Wayland ne compose pas correctement la fenêtre pywebview
# (fenêtre créée mais jamais affichée) ; XWayland (la couche de compatibilité X11)
# fonctionne. Doit être posé avant que Qt ne soit initialisé par pywebview.
if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import webview

if not getattr(sys, "frozen", False):
    BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from app.services.backup import installer_base_en_attente  # noqa: E402
from app.paths import get_migrations_dir  # noqa: E402
from flask_migrate import upgrade  # noqa: E402

APP_TITLE = "Krilia"

logging.getLogger("werkzeug").setLevel(logging.ERROR)


class DesktopApi:
    """Pont JS -> Python. Le navigateur embarqué (WebView2 / WebKit) ne gère pas
    de façon fiable les téléchargements de fichiers ; on passe donc le contenu
    (encodé base64) depuis le JS et on l'enregistre via une vraie boîte de
    dialogue « Enregistrer sous »."""

    def save_file(self, b64_content: str, suggested_name: str) -> dict:
        import base64

        try:
            windows = webview.windows
            window = windows[0] if windows else None
            if window is None:
                return {"ok": False, "error": "Fenêtre indisponible"}

            result = window.create_file_dialog(webview.SAVE_DIALOG, save_filename=suggested_name)
            if not result:
                return {"ok": False, "cancelled": True}

            path = result[0] if isinstance(result, (list, tuple)) else result
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(b64_content))
            return {"ok": True, "path": str(path)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}


def _webview2_runtime_present() -> bool:
    """Le moteur d'affichage moderne (Microsoft Edge WebView2) est-il installé ?

    Sur Windows, pywebview a besoin de ce composant pour afficher l'interface.
    Il est préinstallé sur Windows 11 et sur les Windows 10 à jour, mais absent
    de beaucoup de postes plus anciens : sans lui, la fenêtre reste blanche.
    """
    if not sys.platform.startswith("win"):
        return True

    import winreg

    subkey = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    candidates = [
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_CURRENT_USER, 0),
    ]
    for root, access_flag in candidates:
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | access_flag) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
                if version and version != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def _show_error(title: str, text: str) -> None:
    if sys.platform.startswith("win"):
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # MB_ICONERROR
    else:
        print(f"{title}\n{text}", file=sys.stderr)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Le serveur backend n'a pas démarré à temps")


WEBVIEW2_DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def main() -> None:
    if not _webview2_runtime_present():
        _show_error(
            "Krilia — composant manquant",
            "Krilia a besoin du composant « Microsoft Edge WebView2 » pour "
            "afficher son interface.\n\n"
            "Il est normalement installé automatiquement. S'il manque, "
            "téléchargez-le gratuitement ici puis relancez Krilia :\n\n"
            f"{WEBVIEW2_DOWNLOAD_URL}",
        )
        return

    installer_base_en_attente()
    app = create_app("production")

    with app.app_context():
        upgrade(directory=str(get_migrations_dir()))

    port = find_free_port()
    server_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "127.0.0.1", "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    server_thread.start()

    url = f"http://127.0.0.1:{port}/"
    wait_for_server(url)

    webview.create_window(
        APP_TITLE, url, width=1400, height=900, min_size=(1024, 700), js_api=DesktopApi()
    )
    # gui explicite : ne jamais retomber sur un moteur d'affichage ancien
    # (qui laisserait l'interface à moitié vide).
    gui = "edgechromium" if sys.platform.startswith("win") else None
    try:
        webview.start(gui=gui)
    except Exception as exc:  # noqa: BLE001
        _show_error(
            "Krilia — affichage impossible",
            "Krilia n'a pas pu ouvrir sa fenêtre.\n\n"
            "Installez « Microsoft Edge WebView2 » puis relancez Krilia :\n"
            f"{WEBVIEW2_DOWNLOAD_URL}\n\n"
            f"Détail technique : {exc}",
        )
        raise


if __name__ == "__main__":
    main()
