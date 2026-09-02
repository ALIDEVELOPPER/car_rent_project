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


def main() -> None:
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
    webview.start()


if __name__ == "__main__":
    main()
