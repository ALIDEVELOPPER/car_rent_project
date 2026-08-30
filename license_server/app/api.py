import secrets
from datetime import timedelta
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import Installation, StatutInstallation, generate_secret, utcnow

public_bp = Blueprint("public", __name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# --- Sérialisation ----------------------------------------------------------


def _public_view(inst: Installation, *, with_secret: bool = False) -> dict:
    data = {
        "installation_id": inst.installation_id,
        "statut": inst.statut.value,
        "essai_expire_le": inst.essai_expire_le.isoformat(),
        "bloque_le": inst.bloque_le.isoformat(),
        "jours_essai_restants": inst.jours_essai_restants,
        "server_time": utcnow().isoformat(),
    }
    if with_secret:
        data["secret"] = inst.secret
    return data


def _admin_view(inst: Installation) -> dict:
    return {
        "id": inst.id,
        "installation_id": inst.installation_id,
        "machine_fingerprint": inst.machine_fingerprint,
        "nom_agence": inst.nom_agence,
        "hostname": inst.hostname,
        "os_info": inst.os_info,
        "email_contact": inst.email_contact,
        "plan": inst.plan,
        "note": inst.note,
        "statut": inst.statut.value,
        "valide": inst.est_valide,
        "jours_essai_restants": inst.jours_essai_restants,
        "essai_expire_le": inst.essai_expire_le.isoformat(),
        "bloque_le": inst.bloque_le.isoformat(),
        "registered_at": inst.registered_at.isoformat(),
        "activated_at": inst.activated_at.isoformat() if inst.activated_at else None,
        "suspended_at": inst.suspended_at.isoformat() if inst.suspended_at else None,
        "last_seen_at": inst.last_seen_at.isoformat(),
    }


def _by_installation_id(installation_id: str) -> Installation | None:
    return db.session.execute(
        db.select(Installation).filter_by(installation_id=installation_id)
    ).scalar_one_or_none()


def _by_fingerprint(fingerprint: str) -> Installation | None:
    return db.session.execute(
        db.select(Installation)
        .filter_by(machine_fingerprint=fingerprint)
        .order_by(Installation.id.desc())
    ).scalars().first()


# --- Endpoints publics (appelés par l'app des clients) ----------------------


@public_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    installation_id = (data.get("installation_id") or "").strip()
    fingerprint = (data.get("machine_fingerprint") or "").strip()
    if not installation_id or not fingerprint:
        return jsonify({"error": "installation_id et machine_fingerprint requis"}), 400

    meta = {
        "nom_agence": (data.get("nom_agence") or None),
        "hostname": (data.get("hostname") or None),
        "os_info": (data.get("os_info") or None),
    }

    # 1. Déjà enregistrée sous cet installation_id -> idempotent.
    inst = _by_installation_id(installation_id)

    # 2. Sinon, même empreinte machine déjà connue -> on réutilise l'installation
    #    existante (et donc son statut : pas de nouvel essai en supprimant le cache).
    if inst is None:
        inst = _by_fingerprint(fingerprint)

    if inst is None:
        inst = Installation(
            installation_id=installation_id,
            machine_fingerprint=fingerprint,
            secret=generate_secret(),
            **meta,
        )
        inst.start_trial()
        db.session.add(inst)
    else:
        # Complète les métadonnées si elles étaient vides, sans écraser un nom déjà saisi.
        for key, value in meta.items():
            if value and not getattr(inst, key):
                setattr(inst, key, value)
        inst.touch()

    db.session.commit()
    return jsonify(_public_view(inst, with_secret=True))


@public_bp.post("/heartbeat")
def heartbeat():
    data = request.get_json(silent=True) or {}
    installation_id = (data.get("installation_id") or "").strip()
    provided_secret = (data.get("secret") or "").strip()
    if not installation_id or not provided_secret:
        return jsonify({"error": "installation_id et secret requis"}), 400

    inst = _by_installation_id(installation_id)
    if inst is None or not secrets.compare_digest(provided_secret, inst.secret):
        return jsonify({"error": "Installation inconnue ou secret invalide"}), 401

    inst.touch()
    db.session.commit()
    return jsonify(_public_view(inst))


# --- Endpoints admin (protégés par un token partagé) ------------------------


def require_admin_token(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config["ADMIN_TOKEN"]
        token = request.headers.get("X-Admin-Token", "")
        if not expected or not secrets.compare_digest(token, expected):
            return jsonify({"error": "Non autorisé"}), 401
        return view(*args, **kwargs)

    return wrapped


@admin_bp.get("/installations")
@require_admin_token
def list_installations():
    query = db.select(Installation).order_by(Installation.last_seen_at.desc())

    statut = request.args.get("statut")
    if statut:
        try:
            query = query.filter(Installation.statut == StatutInstallation(statut))
        except ValueError:
            return jsonify({"error": f"Statut inconnu : {statut}"}), 400

    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Installation.nom_agence.ilike(like),
                Installation.hostname.ilike(like),
                Installation.email_contact.ilike(like),
            )
        )

    installations = db.session.execute(query).scalars().all()
    return jsonify([_admin_view(i) for i in installations])


@admin_bp.get("/installations/<int:inst_id>")
@require_admin_token
def get_installation(inst_id):
    inst = db.session.get(Installation, inst_id)
    if inst is None:
        return jsonify({"error": "Installation introuvable"}), 404
    return jsonify(_admin_view(inst))


@admin_bp.patch("/installations/<int:inst_id>")
@require_admin_token
def update_installation(inst_id):
    inst = db.session.get(Installation, inst_id)
    if inst is None:
        return jsonify({"error": "Installation introuvable"}), 404

    data = request.get_json(silent=True) or {}

    if "statut" in data:
        try:
            nouveau = StatutInstallation(data["statut"])
        except ValueError:
            return jsonify({"error": f"Statut inconnu : {data['statut']}"}), 400
        if nouveau == StatutInstallation.ACTIF:
            inst.approve()
        elif nouveau == StatutInstallation.SUSPENDU:
            inst.block()
        else:
            inst.statut = StatutInstallation.ESSAI

    for field in ("email_contact", "plan", "note"):
        if field in data:
            setattr(inst, field, (data[field] or None))

    db.session.commit()
    return jsonify(_admin_view(inst))


@admin_bp.post("/installations/<int:inst_id>/approve")
@require_admin_token
def approve_installation(inst_id):
    inst = db.session.get(Installation, inst_id)
    if inst is None:
        return jsonify({"error": "Installation introuvable"}), 404
    inst.approve()
    db.session.commit()
    return jsonify(_admin_view(inst))


@admin_bp.post("/installations/<int:inst_id>/block")
@require_admin_token
def block_installation(inst_id):
    inst = db.session.get(Installation, inst_id)
    if inst is None:
        return jsonify({"error": "Installation introuvable"}), 404
    inst.block()
    db.session.commit()
    return jsonify(_admin_view(inst))


@admin_bp.post("/installations/<int:inst_id>/extend")
@require_admin_token
def extend_trial(inst_id):
    inst = db.session.get(Installation, inst_id)
    if inst is None:
        return jsonify({"error": "Installation introuvable"}), 404

    data = request.get_json(silent=True) or {}
    try:
        days = int(data.get("days", 7))
    except (TypeError, ValueError):
        return jsonify({"error": "days doit être un entier"}), 400
    if not 1 <= days <= 365:
        return jsonify({"error": "days doit être entre 1 et 365"}), 400

    # Prolonge à partir de la date d'expiration si elle est dans le futur,
    # sinon à partir de maintenant.
    base = max(inst.essai_expire_le, utcnow())
    inst.essai_expire_le = base + timedelta(days=days)
    inst.statut = StatutInstallation.ESSAI
    inst.suspended_at = None
    db.session.commit()
    return jsonify(_admin_view(inst))


@admin_bp.delete("/installations/<int:inst_id>")
@require_admin_token
def delete_installation(inst_id):
    inst = db.session.get(Installation, inst_id)
    if inst is None:
        return jsonify({"error": "Installation introuvable"}), 404
    db.session.delete(inst)
    db.session.commit()
    return "", 204
