from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "nom": user.nom,
        "email": user.email,
        "role": user.role.value,
    }


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    mot_de_passe = data.get("mot_de_passe") or ""

    if not email or not mot_de_passe:
        return jsonify({"error": "Email et mot de passe requis"}), 400

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

    if user is None or not user.actif or not user.check_password(mot_de_passe):
        return jsonify({"error": "Email ou mot de passe incorrect"}), 401

    login_user(user)
    user.last_login = datetime.now(UTC)
    db.session.commit()

    return jsonify(_serialize_user(user))


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return "", 204


@bp.get("/me")
@login_required
def me():
    return jsonify(_serialize_user(current_user))
