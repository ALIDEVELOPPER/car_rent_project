from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import User
from app.models.enums import RoleUser

bp = Blueprint("setup", __name__, url_prefix="/api/setup")


def _needs_setup() -> bool:
    count = db.session.execute(db.select(db.func.count()).select_from(User)).scalar_one()
    return count == 0


@bp.get("/status")
def status():
    return jsonify({"needs_setup": _needs_setup()})


@bp.post("/admin")
def create_first_admin():
    if not _needs_setup():
        return jsonify({"error": "La configuration initiale a déjà été effectuée"}), 409

    data = request.get_json(silent=True) or {}
    missing = [f for f in ("nom", "email", "mot_de_passe") if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    if len(data["mot_de_passe"]) < 8:
        return jsonify({"error": "Le mot de passe doit contenir au moins 8 caractères"}), 400

    user = User(nom=data["nom"], email=data["email"].strip().lower(), role=RoleUser.ADMIN)
    user.set_password(data["mot_de_passe"])
    db.session.add(user)
    db.session.commit()

    return jsonify({"email": user.email}), 201
