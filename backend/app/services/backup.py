"""Sauvegarde et restauration de toutes les données locales (base + fichiers).

La sauvegarde est une archive .zip (chiffrée AES si un mot de passe est fourni)
contenant la base SQLite, les documents/photos et un petit manifeste.

La restauration ne remplace PAS la base à chaud (des connexions SQLite sont
ouvertes). Elle dépose la nouvelle base à côté sous le nom `app.db.incoming` :
au prochain démarrage, `desktop/main.py` (ou create_app) l'installe. Les
fichiers d'upload, eux, sont remplacés immédiatement.
"""
import io
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pyzipper
from flask import current_app

from app.paths import get_app_data_dir

MANIFEST_NOM = "manifest.json"
FORMAT_VERSION = 1


def _db_path() -> Path | None:
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        return None
    return Path(uri.replace("sqlite:///", "", 1))


def _uploads_path() -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"])


def creer_sauvegarde(password: str | None = None) -> tuple[bytes, str]:
    db_path = _db_path()
    uploads = _uploads_path()

    buf = io.BytesIO()
    zf_args = {"compression": pyzipper.ZIP_DEFLATED}
    if password:
        zf_args["encryption"] = pyzipper.WZ_AES

    with pyzipper.AESZipFile(buf, "w", **zf_args) as zf:
        if password:
            zf.setpassword(password.encode("utf-8"))

        manifest = {
            "format": FORMAT_VERSION,
            "cree_le": datetime.now(UTC).isoformat(),
            "chiffre": bool(password),
        }
        zf.writestr(MANIFEST_NOM, json.dumps(manifest, ensure_ascii=False, indent=2))

        if db_path and db_path.exists():
            zf.write(db_path, "app.db")

        if uploads.exists():
            for f in uploads.rglob("*"):
                if f.is_file():
                    zf.write(f, f"uploads/{f.relative_to(uploads).as_posix()}")

    nom = f"krilia-sauvegarde-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"
    return buf.getvalue(), nom


class RestaurationError(ValueError):
    pass


def restaurer_sauvegarde(zip_bytes: bytes, password: str | None = None) -> dict:
    data_dir = get_app_data_dir()
    uploads = _uploads_path()

    try:
        with pyzipper.AESZipFile(io.BytesIO(zip_bytes), "r") as zf:
            if password:
                zf.setpassword(password.encode("utf-8"))
            noms = zf.namelist()
            if MANIFEST_NOM not in noms:
                raise RestaurationError("Fichier de sauvegarde invalide (manifeste absent).")
            try:
                manifest = json.loads(zf.read(MANIFEST_NOM))
            except (RuntimeError, json.JSONDecodeError):
                raise RestaurationError("Mot de passe incorrect ou archive corrompue.") from None
            if manifest.get("format") != FORMAT_VERSION:
                raise RestaurationError("Version de sauvegarde non compatible.")
            if "app.db" not in noms:
                raise RestaurationError("La sauvegarde ne contient pas de base de données.")

            try:
                db_bytes = zf.read("app.db")
            except RuntimeError:
                raise RestaurationError("Mot de passe incorrect.") from None

            # Base : déposée pour installation au prochain démarrage.
            incoming = data_dir / "app.db.incoming"
            incoming.write_bytes(db_bytes)

            # Uploads : remplacés tout de suite.
            if uploads.exists():
                shutil.rmtree(uploads)
            uploads.mkdir(parents=True, exist_ok=True)
            for nom in noms:
                if nom.startswith("uploads/") and not nom.endswith("/"):
                    cible = uploads / nom[len("uploads/"):]
                    cible.parent.mkdir(parents=True, exist_ok=True)
                    cible.write_bytes(zf.read(nom))
    except pyzipper.BadZipFile:
        raise RestaurationError("Le fichier n'est pas une archive valide.") from None

    return {"restart_required": True}


def installer_base_en_attente() -> bool:
    """Appelé au démarrage : si une base restaurée attend, l'installe."""
    data_dir = get_app_data_dir()
    incoming = data_dir / "app.db.incoming"
    if not incoming.exists():
        return False
    cible = data_dir / "app.db"
    if cible.exists():
        cible.replace(data_dir / "app.db.avant-restauration")
    incoming.replace(cible)
    return True
