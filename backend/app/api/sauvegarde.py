import io

from flask import Blueprint, jsonify, request, send_file

from app.models.enums import RoleUser
from app.services.backup import RestaurationError, creer_sauvegarde, restaurer_sauvegarde
from app.utils.decorators import role_required

bp = Blueprint("sauvegarde", __name__, url_prefix="/api/sauvegarde")


@bp.post("")
@role_required(RoleUser.ADMIN)
def creer():
    data = request.get_json(silent=True) or {}
    password = (data.get("password") or "").strip() or None
    contenu, nom = creer_sauvegarde(password)
    return send_file(
        io.BytesIO(contenu),
        mimetype="application/zip",
        as_attachment=True,
        download_name=nom,
    )


@bp.post("/restauration")
@role_required(RoleUser.ADMIN)
def restaurer():
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    password = (request.form.get("password") or "").strip() or None
    try:
        resultat = restaurer_sauvegarde(fichier.read(), password)
    except RestaurationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(resultat)
