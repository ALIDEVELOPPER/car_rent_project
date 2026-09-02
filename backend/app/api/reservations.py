import io
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Client, Reservation, Vehicule
from app.models.enums import SourceReservation, StatutCaution, StatutReservation
from app.services.availability import is_vehicule_available, vehicule_reservable
from app.services.contract import contrat_disponible, render_contrat_pdf
from app.services.invoicing import create_facture_for_reservation
from app.services.pricing import compute_montant_total
from app.services.reservation_lifecycle import InvalidTransitionError, apply_statut_transition

bp = Blueprint("reservations", __name__, url_prefix="/api/reservations")


def _serialize_reservation(reservation: Reservation) -> dict:
    return {
        "id": reservation.id,
        "client_id": reservation.client_id,
        "vehicule_id": reservation.vehicule_id,
        "created_by": reservation.created_by,
        "date_debut": reservation.date_debut.isoformat(),
        "date_fin": reservation.date_fin.isoformat(),
        "heure_debut": reservation.heure_debut,
        "heure_fin": reservation.heure_fin,
        "statut": reservation.statut.value,
        "prix_jour_applique": str(reservation.prix_jour_applique),
        "montant_total": str(reservation.montant_total),
        "caution": str(reservation.caution),
        "caution_statut": reservation.caution_statut.value,
        "caution_retenue": str(reservation.caution_retenue) if reservation.caution_retenue is not None else None,
        "caution_note": reservation.caution_note,
        "lieu_prise_en_charge": reservation.lieu_prise_en_charge,
        "source": reservation.source.value if reservation.source else None,
        "notes": reservation.notes,
        "created_at": reservation.created_at.isoformat(),
        "facture_id": reservation.facture.id if reservation.facture else None,
    }


def _parse_caution(raw) -> Decimal:
    if raw in (None, ""):
        return Decimal("0")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Caution invalide : {raw!r}") from None
    if value < 0:
        raise ValueError("La caution ne peut pas être négative")
    return value


def _parse_date(raw, field_name: str) -> date:
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Date invalide pour '{field_name}' : {raw!r}") from None


def _parse_source(raw) -> SourceReservation | None:
    if raw in (None, ""):
        return None
    try:
        return SourceReservation(raw)
    except ValueError:
        raise ValueError(f"Canal d'acquisition inconnu : {raw}") from None


def _parse_heure(raw) -> str | None:
    if raw in (None, ""):
        return None
    raw = str(raw).strip()
    parts = raw.split(":")
    try:
        h, m = int(parts[0]), int(parts[1])
        if len(parts) == 2 and 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except (ValueError, IndexError):
        pass
    raise ValueError(f"Heure invalide : {raw!r}")


@bp.get("")
@login_required
def list_reservations():
    query = db.select(Reservation).order_by(Reservation.date_debut.desc())

    vehicule_id = request.args.get("vehicule_id", type=int)
    if vehicule_id is not None:
        query = query.filter(Reservation.vehicule_id == vehicule_id)

    client_id = request.args.get("client_id", type=int)
    if client_id is not None:
        query = query.filter(Reservation.client_id == client_id)

    statut = request.args.get("statut", "").strip()
    if statut:
        try:
            query = query.filter(Reservation.statut == StatutReservation(statut))
        except ValueError:
            return jsonify({"error": f"Statut inconnu : {statut}"}), 400

    reservations = db.session.execute(query).scalars().all()
    return jsonify([_serialize_reservation(r) for r in reservations])


@bp.post("")
@login_required
def create_reservation():
    data = request.get_json(silent=True) or {}

    missing = [f for f in ("client_id", "vehicule_id", "date_debut", "date_fin") if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    client_obj = db.session.get(Client, data["client_id"])
    if client_obj is None:
        return jsonify({"error": "Client introuvable"}), 404

    vehicule = db.session.get(Vehicule, data["vehicule_id"])
    if vehicule is None:
        return jsonify({"error": "Véhicule introuvable"}), 404

    if not vehicule_reservable(vehicule):
        return jsonify({"error": "Ce véhicule est en maintenance ou hors service : il ne peut pas être réservé."}), 409

    try:
        date_debut = _parse_date(data["date_debut"], "date_debut")
        date_fin = _parse_date(data["date_fin"], "date_fin")
        montant_total = compute_montant_total(vehicule.tarif_jour, date_debut, date_fin)
        caution = _parse_caution(data.get("caution"))
        heure_debut = _parse_heure(data.get("heure_debut"))
        heure_fin = _parse_heure(data.get("heure_fin"))
        source = _parse_source(data.get("source"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not is_vehicule_available(vehicule.id, date_debut, date_fin):
        return jsonify({"error": "Le véhicule n'est pas disponible sur ces dates"}), 409

    reservation = Reservation(
        client_id=client_obj.id,
        vehicule_id=vehicule.id,
        created_by=current_user.id,
        date_debut=date_debut,
        date_fin=date_fin,
        prix_jour_applique=vehicule.tarif_jour,
        montant_total=montant_total,
        caution=caution,
        heure_debut=heure_debut,
        heure_fin=heure_fin,
        lieu_prise_en_charge=(data.get("lieu_prise_en_charge") or None),
        source=source,
        notes=data.get("notes"),
    )
    db.session.add(reservation)
    db.session.commit()
    return jsonify(_serialize_reservation(reservation)), 201


@bp.get("/<int:reservation_id>")
@login_required
def get_reservation(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404
    return jsonify(_serialize_reservation(reservation))


@bp.put("/<int:reservation_id>")
@login_required
def update_reservation(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404

    if reservation.statut in (StatutReservation.TERMINEE, StatutReservation.ANNULEE):
        return jsonify({"error": "Une réservation terminée ou annulée n'est plus modifiable"}), 409

    data = request.get_json(silent=True) or {}

    try:
        date_debut = (
            _parse_date(data["date_debut"], "date_debut")
            if "date_debut" in data
            else reservation.date_debut
        )
        date_fin = (
            _parse_date(data["date_fin"], "date_fin") if "date_fin" in data else reservation.date_fin
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    vehicule_id = data.get("vehicule_id", reservation.vehicule_id)
    vehicule_changed = vehicule_id != reservation.vehicule_id

    if vehicule_changed:
        vehicule = db.session.get(Vehicule, vehicule_id)
        if vehicule is None:
            return jsonify({"error": "Véhicule introuvable"}), 404
        if not vehicule_reservable(vehicule):
            return jsonify({"error": "Ce véhicule est en maintenance ou hors service : il ne peut pas être réservé."}), 409
    else:
        vehicule = reservation.vehicule

    dates_changed = date_debut != reservation.date_debut or date_fin != reservation.date_fin

    if dates_changed or vehicule_changed:
        try:
            prix_jour = vehicule.tarif_jour if vehicule_changed else reservation.prix_jour_applique
            montant_total = compute_montant_total(prix_jour, date_debut, date_fin)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if not is_vehicule_available(vehicule.id, date_debut, date_fin, exclude_reservation_id=reservation.id):
            return jsonify({"error": "Le véhicule n'est pas disponible sur ces dates"}), 409

        reservation.date_debut = date_debut
        reservation.date_fin = date_fin
        reservation.vehicule_id = vehicule.id
        reservation.prix_jour_applique = prix_jour
        reservation.montant_total = montant_total

    if "client_id" in data:
        client_obj = db.session.get(Client, data["client_id"])
        if client_obj is None:
            return jsonify({"error": "Client introuvable"}), 404
        reservation.client_id = client_obj.id

    if "notes" in data:
        reservation.notes = data["notes"]

    if "lieu_prise_en_charge" in data:
        reservation.lieu_prise_en_charge = data["lieu_prise_en_charge"] or None

    if "source" in data:
        try:
            reservation.source = _parse_source(data["source"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    for champ in ("heure_debut", "heure_fin"):
        if champ in data:
            try:
                setattr(reservation, champ, _parse_heure(data[champ]))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

    if "caution" in data:
        try:
            reservation.caution = _parse_caution(data["caution"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    err = _apply_caution_fields(reservation, data)
    if err:
        return jsonify({"error": err}), 400

    db.session.commit()
    return jsonify(_serialize_reservation(reservation))


def _apply_caution_fields(reservation: Reservation, data: dict) -> str | None:
    """Applique caution_statut / caution_retenue / caution_note. Renvoie un
    message d'erreur ou None."""
    if "caution_statut" in data:
        try:
            reservation.caution_statut = StatutCaution(data["caution_statut"])
        except ValueError:
            return f"Statut de caution inconnu : {data['caution_statut']}"

    if "caution_retenue" in data:
        raw = data["caution_retenue"]
        if raw in (None, ""):
            reservation.caution_retenue = None
        else:
            try:
                montant = Decimal(str(raw))
            except (InvalidOperation, TypeError):
                return "Montant retenu invalide"
            if montant < 0 or montant > reservation.caution:
                return "Le montant retenu doit être entre 0 et la caution"
            reservation.caution_retenue = montant

    if "caution_note" in data:
        reservation.caution_note = data["caution_note"] or None

    if reservation.caution_statut != StatutCaution.RETENUE:
        reservation.caution_retenue = None
    return None


@bp.patch("/<int:reservation_id>/statut")
@login_required
def change_statut(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404

    data = request.get_json(silent=True) or {}
    raw_statut = data.get("statut")
    if not raw_statut:
        return jsonify({"error": "Le champ 'statut' est requis"}), 400

    try:
        nouveau_statut = StatutReservation(raw_statut)
    except ValueError:
        return jsonify({"error": f"Statut inconnu : {raw_statut}"}), 400

    try:
        apply_statut_transition(reservation, nouveau_statut)
    except InvalidTransitionError as exc:
        return jsonify({"error": str(exc)}), 409

    if nouveau_statut == StatutReservation.TERMINEE:
        create_facture_for_reservation(reservation)

    db.session.commit()
    return jsonify(_serialize_reservation(reservation))


@bp.patch("/<int:reservation_id>/caution")
@login_required
def update_caution(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404

    data = request.get_json(silent=True) or {}
    # accepte les clés courtes (statut/retenue/note) ou longues (caution_*)
    mapped = {f"caution_{k}" if k in ("statut", "retenue", "note") else k: v for k, v in data.items()}
    err = _apply_caution_fields(reservation, mapped)
    if err:
        return jsonify({"error": err}), 400

    db.session.commit()
    return jsonify(_serialize_reservation(reservation))


@bp.get("/<int:reservation_id>/contrat/pdf")
@login_required
def download_contrat(reservation_id):
    reservation = db.session.get(Reservation, reservation_id)
    if reservation is None:
        return jsonify({"error": "Réservation introuvable"}), 404

    if not contrat_disponible(reservation):
        return jsonify({"error": "Aucun contrat pour une réservation annulée"}), 409

    pdf_bytes = render_contrat_pdf(reservation)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"contrat-{reservation.id:05d}.pdf",
    )
