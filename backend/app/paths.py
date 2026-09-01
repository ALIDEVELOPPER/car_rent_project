import os
import sys
from pathlib import Path

APP_NAME = "AgenceLocation"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_frontend_dir() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS) / "frontend"
    return Path(__file__).resolve().parent.parent.parent / "frontend"


def get_migrations_dir() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS) / "migrations"
    return Path(__file__).resolve().parent.parent / "migrations"


def get_assets_dir() -> Path:
    """Ressources embarquées (polices PDF, etc.)."""
    if is_frozen():
        return Path(sys._MEIPASS) / "app" / "assets"
    return Path(__file__).resolve().parent / "assets"


def get_app_data_dir() -> Path:
    """Dossier persistant pour la base de données, les uploads et la clé secrète.

    En dev : backend/instance/ (comportement historique, inchangé).
    En exécutable packagé : un vrai dossier de données utilisateur, car le
    dossier d'installation peut être en lecture seule ou (en mode --onefile)
    temporaire et effacé à chaque lancement.
    """
    if not is_frozen():
        return Path(__file__).resolve().parent.parent / "instance"

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))

    data_dir = base / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
