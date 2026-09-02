from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models import DepenseVehicule, Vehicule
from app.models.enums import TypeDepense

bp = Blueprint("depenses", __name__, url_prefix="/api")


def _serialize(depense: DepenseVehicule) -> dict:
    return {
        "id": depense.id,
        "vehicule_id": depense.vehicule_id,
        "type": depense.type.value,
        "montant": str(depense.montant),
        "date_depense": depense.date_depense.isoformat(),
        "note": depense.note,
    }


def _parse_payload(data: dict) -> tuple[dict | None, str | None]:
    champs = {}

    if "type" in data:
        try:
            champs["type"] = TypeDepense(data["type"])
        except ValueError:
            return None, f"Type de dépense inconnu : {data['type']}"

    if "montant" in data:
        from decimal import Decimal, InvalidOperation

        try:
            montant = Decimal(str(data["montant"]))
        except (InvalidOperation, TypeError):
            return None, "Montant invalide"
        if montant < 0:
            return None, "Le montant ne peut pas être négatif"
        champs["montant"] = montant

    if "date_depense" in data:
        try:
            champs["date_depense"] = date.fromisoformat(data["date_depense"])
        except (TypeError, ValueError):
            return None, "Date invalide (attendu : AAAA-MM-JJ)"

    if "note" in data:
        champs["note"] = data["note"] or None

    return champs, None


@bp.get("/vehicules/<int:vehicule_id>/depenses")
@login_required
def liste(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404
    depenses = sorted(vehicule.depenses, key=lambda d: d.date_depense, reverse=True)
    return jsonify([_serialize(d) for d in depenses])


@bp.post("/vehicules/<int:vehicule_id>/depenses")
@login_required
def creer(vehicule_id):
    vehicule = db.session.get(Vehicule, vehicule_id)
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404

    data = request.get_json(silent=True) or {}
    for requis in ("type", "montant", "date_depense"):
        if not data.get(requis):
            return jsonify({"error": f"Champ requis manquant : {requis}"}), 400

    champs, err = _parse_payload(data)
    if err:
        return jsonify({"error": err}), 400

    depense = DepenseVehicule(vehicule_id=vehicule.id, **champs)
    db.session.add(depense)
    db.session.commit()
    return jsonify(_serialize(depense)), 201


@bp.put("/depenses/<int:depense_id>")
@login_required
def modifier(depense_id):
    depense = db.session.get(DepenseVehicule, depense_id)
    if depense is None:
        return jsonify({"error": "Dépense introuvable"}), 404

    champs, err = _parse_payload(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    for key, value in champs.items():
        setattr(depense, key, value)
    db.session.commit()
    return jsonify(_serialize(depense))


@bp.delete("/depenses/<int:depense_id>")
@login_required
def supprimer(depense_id):
    depense = db.session.get(DepenseVehicule, depense_id)
    if depense is None:
        return jsonify({"error": "Dépense introuvable"}), 404
    db.session.delete(depense)
    db.session.commit()
    return "", 204
