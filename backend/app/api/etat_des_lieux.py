import io

from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required

from app.extensions import db
from app.models import EtatDesLieux, Reservation
from app.models.enums import NiveauCarburant, TypeEtatDesLieux
from app.utils.uploads import ALLOWED_IMAGE_EXTENSIONS, UploadError, save_upload

bp = Blueprint("etat_des_lieux", __name__, url_prefix="/api")


def _serialize(etat: EtatDesLieux) -> dict:
    return {
        "id": etat.id,
        "reservation_id": etat.reservation_id,
        "type": etat.type.value,
        "date_effectue": etat.date_effectue.isoformat(),
        "kilometrage": etat.kilometrage,
        "niveau_carburant": etat.niveau_carburant.value if etat.niveau_carburant else None,
        "degats": etat.degats,
        "observations": etat.observations,
        "photos": etat.photos_liste,
    }


@bp.get("/reservations/<int:reservation_id>/etats-des-lieux")
@login_required
def liste(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404
    return jsonify([_serialize(e) for e in reservation.etats_des_lieux])


@bp.put("/reservations/<int:reservation_id>/etats-des-lieux/<string:type_>")
@login_required
def upsert(reservation_id, type_):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404
    try:
        type_edl = TypeEtatDesLieux(type_)
    except ValueError:
        return jsonify({"error": f"Type inconnu : {type_}"}), 400

    etat = next((e for e in reservation.etats_des_lieux if e.type == type_edl), None)
    if etat is None:
        etat = EtatDesLieux(reservation_id=reservation.id, type=type_edl)
        db.session.add(etat)

    data = request.get_json(silent=True) or {}

    if "kilometrage" in data:
        raw = data["kilometrage"]
        try:
            etat.kilometrage = int(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return jsonify({"error": "Kilométrage invalide"}), 400

    if "niveau_carburant" in data:
        raw = data["niveau_carburant"]
        if raw in (None, ""):
            etat.niveau_carburant = None
        else:
            try:
                etat.niveau_carburant = NiveauCarburant(raw)
            except ValueError:
                return jsonify({"error": f"Niveau de carburant inconnu : {raw}"}), 400

    for champ in ("degats", "observations"):
        if champ in data:
            setattr(etat, champ, data[champ] or None)

    db.session.commit()
    return jsonify(_serialize(etat))


def _get_etat(etat_id):
    return db.session.get(EtatDesLieux, etat_id)


@bp.post("/etat-des-lieux/<int:etat_id>/photo")
@login_required
def ajouter_photo(etat_id):
    etat = _get_etat(etat_id)
    if etat is None:
        return jsonify({"error": "État des lieux introuvable"}), 404
    try:
        relative_path = save_upload(
            request.files.get("fichier"),
            subdir=f"etats-des-lieux/{etat.id}",
            allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
        )
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400
    etat.ajouter_photo(relative_path)
    db.session.commit()
    return jsonify(_serialize(etat))


@bp.delete("/etat-des-lieux/<int:etat_id>/photo")
@login_required
def retirer_photo(etat_id):
    etat = _get_etat(etat_id)
    if etat is None:
        return jsonify({"error": "État des lieux introuvable"}), 404
    url = (request.get_json(silent=True) or {}).get("url")
    etat.photos = "\n".join(p for p in etat.photos_liste if p != url)
    db.session.commit()
    return jsonify(_serialize(etat))


@bp.get("/etat-des-lieux/<int:etat_id>/pdf")
@login_required
def pdf(etat_id):
    etat = _get_etat(etat_id)
    if etat is None:
        return jsonify({"error": "État des lieux introuvable"}), 404
    from app.services.etat_des_lieux_pdf import render_etat_des_lieux_pdf

    contenu = render_etat_des_lieux_pdf(etat)
    return send_file(
        io.BytesIO(contenu),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"etat-des-lieux-{etat.type.value}-{etat.reservation_id:05d}.pdf",
    )
