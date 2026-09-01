from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Agence, User
from app.models.enums import RoleUser
from app.services.agence import get_or_create_agence
from app.utils.decorators import role_required
from app.utils.uploads import ALLOWED_IMAGE_EXTENSIONS, UploadError, save_upload

bp = Blueprint("parametres", __name__, url_prefix="/api/parametres")


# --- Agence -----------------------------------------------------------------


def _serialize_agence(agence: Agence) -> dict:
    return {
        "id": agence.id,
        "nom": agence.nom,
        "adresse": agence.adresse,
        "telephone": agence.telephone,
        "email": agence.email,
        "logo_url": agence.logo_url,
        "mentions_legales": agence.mentions_legales,
        "conditions_contrat": agence.conditions_contrat,
        "langue": agence.langue,
    }


LANGUES_SUPPORTEES = ("fr", "ar")


@bp.get("/langue")
def get_langue():
    """Langue de l'interface, accessible sans authentification (écrans login / setup)."""
    agence = db.session.execute(db.select(Agence)).scalar_one_or_none()
    return jsonify({"langue": agence.langue if agence else "fr"})


@bp.get("/agence")
@login_required
def get_agence():
    return jsonify(_serialize_agence(get_or_create_agence()))


@bp.put("/agence")
@role_required(RoleUser.ADMIN)
def update_agence():
    agence = get_or_create_agence()
    data = request.get_json(silent=True) or {}

    if "nom" in data and not data["nom"]:
        return jsonify({"error": "Le nom de l'agence ne peut pas être vide"}), 400

    if "langue" in data and data["langue"] not in LANGUES_SUPPORTEES:
        return jsonify({"error": f"Langue non supportée : {data['langue']}"}), 400

    for field in ("nom", "adresse", "telephone", "email", "mentions_legales", "conditions_contrat", "langue"):
        if field in data:
            setattr(agence, field, data[field])

    db.session.commit()
    return jsonify(_serialize_agence(agence))


@bp.post("/agence/logo")
@role_required(RoleUser.ADMIN)
def upload_logo():
    agence = get_or_create_agence()

    try:
        relative_path = save_upload(
            request.files.get("fichier"), subdir="agence/logo", allowed_extensions=ALLOWED_IMAGE_EXTENSIONS
        )
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400

    agence.logo_url = relative_path
    db.session.commit()
    return jsonify(_serialize_agence(agence))


# --- Utilisateurs -------------------------------------------------------------


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "nom": user.nom,
        "email": user.email,
        "role": user.role.value,
        "actif": user.actif,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _is_last_active_admin(user: User) -> bool:
    if user.role != RoleUser.ADMIN or not user.actif:
        return False
    count = db.session.execute(
        db.select(db.func.count())
        .select_from(User)
        .filter(User.role == RoleUser.ADMIN, User.actif.is_(True))
    ).scalar_one()
    return count <= 1


@bp.get("/utilisateurs")
@role_required(RoleUser.ADMIN)
def list_utilisateurs():
    users = db.session.execute(db.select(User).order_by(User.nom)).scalars().all()
    return jsonify([_serialize_user(u) for u in users])


@bp.post("/utilisateurs")
@role_required(RoleUser.ADMIN)
def create_utilisateur():
    data = request.get_json(silent=True) or {}
    missing = [f for f in ("nom", "email", "mot_de_passe") if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    try:
        role = RoleUser(data.get("role", RoleUser.EMPLOYE.value))
    except ValueError:
        return jsonify({"error": f"Rôle inconnu : {data['role']}"}), 400

    user = User(nom=data["nom"], email=data["email"].strip().lower(), role=role)
    user.set_password(data["mot_de_passe"])

    db.session.add(user)
    try:
        db.session.commit()
    except db.exc.IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Cet email existe déjà"}), 409

    return jsonify(_serialize_user(user)), 201


@bp.get("/utilisateurs/<int:user_id>")
@role_required(RoleUser.ADMIN)
def get_utilisateur(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Utilisateur introuvable"}), 404
    return jsonify(_serialize_user(user))


@bp.put("/utilisateurs/<int:user_id>")
@role_required(RoleUser.ADMIN)
def update_utilisateur(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}

    if "nom" in data:
        if not data["nom"]:
            return jsonify({"error": "Le nom ne peut pas être vide"}), 400
        user.nom = data["nom"]

    if "email" in data:
        if not data["email"]:
            return jsonify({"error": "L'email ne peut pas être vide"}), 400
        user.email = data["email"].strip().lower()

    if "role" in data:
        try:
            nouveau_role = RoleUser(data["role"])
        except ValueError:
            return jsonify({"error": f"Rôle inconnu : {data['role']}"}), 400
        if nouveau_role != RoleUser.ADMIN and _is_last_active_admin(user):
            return jsonify({"error": "Impossible de retirer le rôle admin au dernier administrateur"}), 409
        user.role = nouveau_role

    if data.get("mot_de_passe"):
        user.set_password(data["mot_de_passe"])

    try:
        db.session.commit()
    except db.exc.IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Cet email existe déjà"}), 409

    return jsonify(_serialize_user(user))


@bp.patch("/utilisateurs/<int:user_id>/actif")
@role_required(RoleUser.ADMIN)
def toggle_actif(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    if "actif" not in data:
        return jsonify({"error": "Le champ 'actif' est requis"}), 400

    nouveau_actif = bool(data["actif"])
    if not nouveau_actif and _is_last_active_admin(user):
        return jsonify({"error": "Impossible de désactiver le dernier administrateur actif"}), 409

    user.actif = nouveau_actif
    db.session.commit()
    return jsonify(_serialize_user(user))


@bp.delete("/utilisateurs/<int:user_id>")
@role_required(RoleUser.ADMIN)
def delete_utilisateur(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    if user.id == current_user.id:
        return jsonify({"error": "Vous ne pouvez pas supprimer votre propre compte"}), 400

    if _is_last_active_admin(user):
        return jsonify({"error": "Impossible de supprimer le dernier administrateur actif"}), 409

    db.session.delete(user)
    try:
        db.session.commit()
    except db.exc.IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Impossible de supprimer un utilisateur ayant créé des réservations"}), 409

    return "", 204
