from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models import Client
from app.models.enums import RoleUser, TypePieceIdentite
from app.utils.decorators import role_required
from app.utils.uploads import UploadError, save_upload

bp = Blueprint("clients", __name__, url_prefix="/api/clients")

REQUIRED_FIELDS = ("nom", "prenom", "telephone")
EDITABLE_FIELDS = (
    "nom", "prenom", "telephone", "email", "adresse",
    "numero_piece_identite", "numero_permis",
)


def _serialize_client(client: Client, include_reservations: bool = False) -> dict:
    data = {
        "id": client.id,
        "nom": client.nom,
        "prenom": client.prenom,
        "telephone": client.telephone,
        "email": client.email,
        "adresse": client.adresse,
        "date_naissance": client.date_naissance.isoformat() if client.date_naissance else None,
        "type_piece_identite": client.type_piece_identite.value if client.type_piece_identite else None,
        "numero_piece_identite": client.numero_piece_identite,
        "numero_permis": client.numero_permis,
        "date_delivrance_permis": client.date_delivrance_permis.isoformat() if client.date_delivrance_permis else None,
        "document_identite_url": client.document_identite_url,
        "permis_url": client.permis_url,
        "created_at": client.created_at.isoformat(),
    }
    if include_reservations:
        data["reservations"] = [
            {
                "id": r.id,
                "vehicule_id": r.vehicule_id,
                "date_debut": r.date_debut.isoformat(),
                "date_fin": r.date_fin.isoformat(),
                "statut": r.statut.value,
                "montant_total": str(r.montant_total),
            }
            for r in client.reservations
        ]
    return data


def _apply_client_fields(client: Client, data: dict) -> None:
    for field in EDITABLE_FIELDS:
        if field in data:
            setattr(client, field, data[field])

    if "date_naissance" in data:
        raw = data["date_naissance"]
        client.date_naissance = date.fromisoformat(raw) if raw else None

    if "date_delivrance_permis" in data:
        raw = data["date_delivrance_permis"]
        client.date_delivrance_permis = date.fromisoformat(raw) if raw else None

    if "type_piece_identite" in data:
        raw = data["type_piece_identite"]
        client.type_piece_identite = TypePieceIdentite(raw) if raw else None


@bp.get("")
@login_required
def list_clients():
    query = db.select(Client).order_by(Client.nom, Client.prenom)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Client.nom.ilike(like),
                Client.prenom.ilike(like),
                Client.telephone.ilike(like),
                Client.email.ilike(like),
            )
        )

    clients = db.session.execute(query).scalars().all()
    return jsonify([_serialize_client(c) for c in clients])


@bp.post("")
@login_required
def create_client():
    data = request.get_json(silent=True) or {}
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    client = Client(nom=data["nom"], prenom=data["prenom"], telephone=data["telephone"])
    try:
        _apply_client_fields(client, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.add(client)
    db.session.commit()
    return jsonify(_serialize_client(client)), 201


@bp.get("/<int:client_id>")
@login_required
def get_client(client_id):
    client = db.session.get(Client, client_id)
    if client is None:
        return jsonify({"error": "Client introuvable"}), 404
    return jsonify(_serialize_client(client, include_reservations=True))


@bp.put("/<int:client_id>")
@login_required
def update_client(client_id):
    client = db.session.get(Client, client_id)
    if client is None:
        return jsonify({"error": "Client introuvable"}), 404

    data = request.get_json(silent=True) or {}
    try:
        _apply_client_fields(client, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify(_serialize_client(client))


@bp.delete("/<int:client_id>")
@role_required(RoleUser.ADMIN)
def delete_client(client_id):
    client = db.session.get(Client, client_id)
    if client is None:
        return jsonify({"error": "Client introuvable"}), 404

    if client.reservations:
        return jsonify({"error": "Impossible de supprimer un client ayant des réservations"}), 409

    db.session.delete(client)
    db.session.commit()
    return "", 204


@bp.post("/<int:client_id>/document-identite")
@login_required
def upload_document_identite(client_id):
    client = db.session.get(Client, client_id)
    if client is None:
        return jsonify({"error": "Client introuvable"}), 404

    try:
        relative_path = save_upload(request.files.get("fichier"), subdir=f"clients/{client_id}/identite")
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400

    client.document_identite_url = relative_path
    db.session.commit()
    return jsonify(_serialize_client(client))


@bp.post("/<int:client_id>/permis")
@login_required
def upload_permis(client_id):
    client = db.session.get(Client, client_id)
    if client is None:
        return jsonify({"error": "Client introuvable"}), 404

    try:
        relative_path = save_upload(request.files.get("fichier"), subdir=f"clients/{client_id}/permis")
    except UploadError as exc:
        return jsonify({"error": str(exc)}), 400

    client.permis_url = relative_path
    db.session.commit()
    return jsonify(_serialize_client(client))
