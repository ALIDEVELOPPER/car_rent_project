from flask import Blueprint, abort, send_from_directory

from app.paths import get_frontend_dir

FRONTEND_DIR = get_frontend_dir()

bp = Blueprint("web", __name__)

PAGES = {
    "": "dashboard.html",
    "login": "login.html",
    "clients": "clients.html",
    "vehicules": "vehicules.html",
    "reservations": "reservations.html",
    "factures": "factures.html",
    "parametres": "parametres.html",
}


@bp.get("/")
@bp.get("/<path:page>")
def serve_page(page=""):
    filename = PAGES.get(page.strip("/"))
    if filename is None:
        abort(404)
    return send_from_directory(FRONTEND_DIR / "pages", filename)


@bp.get("/static/<path:filename>")
def frontend_static(filename):
    return send_from_directory(FRONTEND_DIR / "static", filename)


@bp.get("/assets/<path:filename>")
def frontend_assets(filename):
    return send_from_directory(FRONTEND_DIR / "assets", filename)
