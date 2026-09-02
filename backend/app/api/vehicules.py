from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models import Vehicule
from app.models.enums import Carburant, RoleUser, StatutVehicule, Transmission
from app.services.availability import is_vehicule_available, vehicule_reservable
from app.utils.decorators import role_required
from app.utils.uploads import ALLOWED_IMAGE_EXTENSIONS, UploadError, save_upload

bp = Blueprint("vehicules", __name__, url_prefix="/api/vehicules")

REQUIRED_FIELDS = ("marque", "modele", "immatriculation", "categorie", "tarif_jour")
EDITABLE_SIMPLE_FIELDS = ("marque", "modele", "immatriculation", "categorie", "couleur")


def _serialize_vehicule(vehicule: Vehicule, include_reservations: bool = False) -> dict:
    data = {
        "id": vehicule.id,
        "marque": vehicule.marque,
        "modele": vehicule.modele,
        "immatriculation": vehicule.immatriculation,
        "categorie": vehicule.categorie,
        "annee": vehicule.annee,
        "couleur": vehicule.couleur,
        "kilometrage": vehicule.kilometrage,
        "carburant": vehicule.carburant.value if vehicule.carburant else None,
        "transmission": vehicule.transmission.value if vehicule.transmission else None,
        "tarif_jour": str(vehicule.tarif_jour),
        "statut": vehicule.statut.value,
        "photo_url": vehicule.photo_url,
        "assurance_expire_le": vehicule.assurance_expire_le.isoformat() if vehicule.assurance_expire_le else None,
        "visite_technique_expire_le": vehicule.visite_technique_expire_le.isoformat() if vehicule.visite_technique_expire_le else None,
        "vignette_expire_le": vehicule.vignette_expire_le.isoformat() if vehicule.vignette_expire_le else None,
        "prochaine_vidange_le": vehicule.prochaine_vidange_le.isoformat() if vehicule.prochaine_vidange_le else None,
        "prochaine_vidange_km": vehicule.prochaine_vidange_km,
        "created_at": vehicule.created_at.isoformat(),
    }
    if include_reservations:
        data["reservations"] = [
            {
                "id": r.id,
                "client_id": r.client_id,
                "date_debut": r.date_debut.isoformat(),
                "date_fin": r.date_fin.isoformat(),
                "statut": r.statut.value,
            }
            for r in vehicule.reservations
        ]
    return data


def _apply_vehicule_fields(vehicule: Vehicule, data: dict) -> None:
    for field in EDITABLE_SIMPLE_FIELDS:
        if field in data:
            setattr(vehicule, field, data[field])

    if "annee" in data:
        vehicule.annee = int(data["annee"]) if data["annee"] not in (None, "") else None

    if "kilometrage" in data:
        vehicule.kilometrage = int(data["kilometrage"]) if data["kilometrage"] not in (None, "") else None

    if "tarif_jour" in data:
        tarif = Decimal(str(data["tarif_jour"]))
        if tarif <= 0:
            raise ValueError("Le tarif journalier doit être positif")
        vehicule.tarif_jour = tarif

    if "carburant" in data:
        raw = data["carburant"]
        vehicule.carburant = Carburant(raw) if raw else None

    if "transmission" in data:
        raw = data["transmission"]
        vehicule.transmission = Transmission(raw) if raw else None

    if "statut" in data:
        raw = data["statut"]
        if raw:
            vehicule.statut = StatutVehicule(raw)

    for champ in ("assurance_expire_le", "visite_technique_expire_le", "vignette_expire_le", "prochaine_vidange_le"):
        if champ in data:
            raw = data[champ]
            setattr(vehicule, champ, date.fromisoformat(raw) if raw else None)

    if "prochaine_vidange_km" in data:
        raw = data["prochaine_vidange_km"]
        vehicule.prochaine_vidange_km = int(raw) if raw not in (None, "") else None


@bp.get("")
@login_required
def list_vehicules():
    query = db.select(Vehicule).order_by(Vehicule.marque, Vehicule.modele)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Vehicule.marque.ilike(like),
                Vehicule.modele.ilike(like),
                Vehicule.immatriculation.ilike(like),
                Vehicule.categorie.ilike(like),
            )
        )

    statut = request.args.get("statut", "").strip()
    if statut:
        try:
            query = query.filter(Vehicule.statut == StatutVehicule(statut))
        except ValueError:
            return jsonify({"error": f"Statut inconnu : {statut}"}), 400

    vehicules = db.session.execute(query).scalars().all()
    return jsonify([_serialize_vehicule(v) for v in vehicules])


@bp.post("")
@login_required
def create_vehicule():
    data = request.get_json(silent=True) or {}
    missing = [f for f in REQUIRED_FIELDS if not data.get(f) and data.get(f) != 0]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    vehicule = Vehicule(
        marque=data["marque"],
        modele=data["modele"],
        immatriculation=data["immatriculation"],
        categorie=data["categorie"],
        tarif_jour=Decimal("0"),
    )
    try:
        _apply_vehicule_fields(vehicule, data)
    except (ValueError, InvalidOperation, TypeError) as exc:
        return jsonify({"error": str(exc) or "Valeur invalide"}), 400

    db.session.add(vehicule)
    try:
        db.session.commit()
    except db.exc.IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Cette immatriculation existe déjà"}), 409

    return jsonify(_serialize_vehicule(vehicule)), 201


@bp.get("/<int:vehicule_id>")
@login_required
def get_vehicule(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404
    return jsonify(_serialize_vehicule(vehicule, include_reservations=True))


@bp.put("/<int:vehicule_id>")
@login_required
def update_vehicule(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404

    data = request.get_json(silent=True) or {}
    try:
        _apply_vehicule_fields(vehicule, data)
    except (ValueError, InvalidOperation, TypeError) as exc:
        return jsonify({"error": str(exc) or "Valeur invalide"}), 400

    try:
        db.session.commit()
    except db.exc.IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Cette immatriculation existe déjà"}), 409

    return jsonify(_serialize_vehicule(vehicule))


@bp.delete("/<int:vehicule_id>")
@role_required(RoleUser.ADMIN)
def delete_vehicule(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404

    if vehicule.reservations:
        return jsonify({"error": "Impossible de supprimer un véhicule ayant des réservations"}), 409

    db.session.delete(vehicule)
    db.session.commit()
    return "", 204


@bp.post("/<int:vehicule_id>/photo")
@login_required
def upload_photo(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404

    try:
        relative_path = save_upload(
            request.files.get("fichier"),
            subdir=f"vehicules/{vehicule_id}/photos",
            allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        )
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400

    vehicule.photo_url = relative_path
    db.session.commit()
    return jsonify(_serialize_vehicule(vehicule))


@bp.get("/<int:vehicule_id>/disponibilite")
@login_required
def check_disponibilite(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404

    raw_debut = request.args.get("date_debut")
    raw_fin = request.args.get("date_fin")
    if not raw_debut or not raw_fin:
        return jsonify({"error": "Paramètres 'date_debut' et 'date_fin' requis"}), 400

    try:
        date_debut = date.fromisoformat(raw_debut)
        date_fin = date.fromisoformat(raw_fin)
    except ValueError:
        return jsonify({"error": "Format de date invalide (attendu : AAAA-MM-JJ)"}), 400

    if not vehicule_reservable(vehicule):
        return jsonify({"disponible": False, "raison": "hors_service"})

    exclude_id = request.args.get("exclude_reservation_id", type=int)
    disponible = is_vehicule_available(vehicule_id, date_debut, date_fin, exclude_reservation_id=exclude_id)
    return jsonify({"disponible": disponible, "raison": None if disponible else "dates_indisponibles"})
