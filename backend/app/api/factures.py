from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask_login import login_required

from app.extensions import db
from app.models import Facture
from app.models.enums import ModePaiement, StatutPaiement
from app.services.invoicing import (
    InvalidPaiementTransitionError,
    apply_paiement_transition,
    save_facture_pdf,
)

bp = Blueprint("factures", __name__, url_prefix="/api/factures")


def _serialize_facture(facture: Facture, include_details: bool = False) -> dict:
    data = {
        "id": facture.id,
        "reservation_id": facture.reservation_id,
        "numero_facture": facture.numero_facture,
        "date_emission": facture.date_emission.isoformat(),
        "montant": str(facture.montant),
        "montant_ht": str(facture.montant_ht) if facture.montant_ht is not None else None,
        "montant_tva": str(facture.montant_tva) if facture.montant_tva is not None else None,
        "taux_tva": str(facture.taux_tva) if facture.taux_tva is not None else None,
        "statut_paiement": facture.statut_paiement.value,
        "mode_paiement": facture.mode_paiement.value if facture.mode_paiement else None,
        "pdf_url": facture.pdf_url,
    }
    if include_details:
        reservation = facture.reservation
        data["date_debut"] = reservation.date_debut.isoformat()
        data["date_fin"] = reservation.date_fin.isoformat()
        data["client"] = {
            "id": reservation.client.id,
            "nom": reservation.client.nom,
            "prenom": reservation.client.prenom,
        }
        data["vehicule"] = {
            "id": reservation.vehicule.id,
            "marque": reservation.vehicule.marque,
            "modele": reservation.vehicule.modele,
            "immatriculation": reservation.vehicule.immatriculation,
        }
    return data


@bp.get("")
@login_required
def list_factures():
    query = db.select(Facture).order_by(Facture.date_emission.desc())

    statut = request.args.get("statut_paiement", "").strip()
    if statut:
        try:
            query = query.filter(Facture.statut_paiement == StatutPaiement(statut))
        except ValueError:
            return jsonify({"error": f"Statut inconnu : {statut}"}), 400

    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(Facture.numero_facture.ilike(f"%{q}%"))

    factures = db.session.execute(query).scalars().all()
    return jsonify([_serialize_facture(f, include_details=True) for f in factures])


@bp.get("/<int:facture_id>")
@login_required
def get_facture(facture_id):
    facture = db.session.get(Facture, facture_id)
    if facture is None:
        return jsonify({"error": "Facture introuvable"}), 404
    return jsonify(_serialize_facture(facture, include_details=True))


@bp.patch("/<int:facture_id>/statut-paiement")
@login_required
def change_statut_paiement(facture_id):
    facture = db.session.get(Facture, facture_id)
    if facture is None:
        return jsonify({"error": "Facture introuvable"}), 404

    data = request.get_json(silent=True) or {}
    raw_statut = data.get("statut_paiement")
    if not raw_statut:
        return jsonify({"error": "Le champ 'statut_paiement' est requis"}), 400

    try:
        nouveau_statut = StatutPaiement(raw_statut)
    except ValueError:
        return jsonify({"error": f"Statut inconnu : {raw_statut}"}), 400

    mode_paiement = None
    raw_mode = data.get("mode_paiement")
    if raw_mode:
        try:
            mode_paiement = ModePaiement(raw_mode)
        except ValueError:
            return jsonify({"error": f"Mode de paiement inconnu : {raw_mode}"}), 400

    try:
        apply_paiement_transition(facture, nouveau_statut, mode_paiement)
    except InvalidPaiementTransitionError as exc:
        return jsonify({"error": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify(_serialize_facture(facture))


@bp.get("/<int:facture_id>/pdf")
@login_required
def download_pdf(facture_id):
    facture = db.session.get(Facture, facture_id)
    if facture is None:
        return jsonify({"error": "Facture introuvable"}), 404

    relative_path = save_facture_pdf(facture)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        relative_path,
        as_attachment=True,
        download_name=f"{facture.numero_facture}.pdf",
    )
