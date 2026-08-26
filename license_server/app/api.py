import secrets
from datetime import timedelta
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import TRIAL_DAYS, Licence, StatutLicence, utcnow

public_bp = Blueprint("public", __name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _serialize(licence: Licence) -> dict:
    return {
        "id": licence.id,
        "code": licence.code,
        "nom_client": licence.nom_client,
        "statut": licence.statut.value,
        "essai_expire_le": licence.essai_expire_le.isoformat() if licence.essai_expire_le else None,
        "activated_at": licence.activated_at.isoformat() if licence.activated_at else None,
        "created_at": licence.created_at.isoformat(),
        "valide": licence.est_valide,
    }


def _get_by_code(code: str) -> Licence | None:
    return db.session.execute(db.select(Licence).filter_by(code=code)).scalar_one_or_none()


# --- Endpoints publics (appelés par l'app des clients) -----------------------


@public_bp.post("/activate")
def activate():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "Code requis"}), 400

    licence = _get_by_code(code)
    if licence is None:
        return jsonify({"error": "Code d'activation invalide"}), 404

    if licence.activated_at is None:
        licence.activated_at = utcnow()
        licence.essai_expire_le = licence.activated_at + timedelta(days=TRIAL_DAYS)
        licence.statut = StatutLicence.ESSAI
        db.session.commit()

    return jsonify(_serialize(licence))


@public_bp.get("/status")
def status():
    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"error": "Code requis"}), 400

    licence = _get_by_code(code)
    if licence is None:
        return jsonify({"error": "Code d'activation invalide"}), 404

    return jsonify(_serialize(licence))


# --- Endpoints admin (protégés par un token partagé) --------------------------


def require_admin_token(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config["ADMIN_TOKEN"]
        token = request.headers.get("X-Admin-Token", "")
        if not expected or not secrets.compare_digest(token, expected):
            return jsonify({"error": "Non autorisé"}), 401
        return view(*args, **kwargs)

    return wrapped


@admin_bp.get("/licences")
@require_admin_token
def list_licences():
    licences = db.session.execute(db.select(Licence).order_by(Licence.created_at.desc())).scalars().all()
    return jsonify([_serialize(l) for l in licences])


@admin_bp.post("/licences")
@require_admin_token
def create_licence():
    data = request.get_json(silent=True) or {}
    nom_client = (data.get("nom_client") or "").strip()
    if not nom_client:
        return jsonify({"error": "nom_client requis"}), 400

    code = (data.get("code") or "").strip() or secrets.token_hex(4).upper()

    licence = Licence(code=code, nom_client=nom_client, statut=StatutLicence.ESSAI)
    db.session.add(licence)
    try:
        db.session.commit()
    except db.exc.IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Ce code existe déjà"}), 409

    return jsonify(_serialize(licence)), 201


@admin_bp.patch("/licences/<int:licence_id>")
@require_admin_token
def update_licence(licence_id):
    licence = db.session.get(Licence, licence_id)
    if licence is None:
        return jsonify({"error": "Licence introuvable"}), 404

    data = request.get_json(silent=True) or {}
    if "statut" in data:
        try:
            licence.statut = StatutLicence(data["statut"])
        except ValueError:
            return jsonify({"error": f"Statut inconnu : {data['statut']}"}), 400

    db.session.commit()
    return jsonify(_serialize(licence))


@admin_bp.delete("/licences/<int:licence_id>")
@require_admin_token
def delete_licence(licence_id):
    licence = db.session.get(Licence, licence_id)
    if licence is None:
        return jsonify({"error": "Licence introuvable"}), 404

    db.session.delete(licence)
    db.session.commit()
    return "", 204
