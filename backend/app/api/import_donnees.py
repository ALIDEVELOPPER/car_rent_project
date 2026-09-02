from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required

from app.models.enums import RoleUser
from app.services.import_excel import (
    import_clients,
    import_vehicules,
    modele_clients_xlsx,
    modele_vehicules_xlsx,
)
from app.utils.decorators import role_required

bp = Blueprint("import_donnees", __name__, url_prefix="/api/import")

_XLSX_EXT = (".xlsx",)


def _fichier_xlsx():
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        return None, (jsonify({"error": "Aucun fichier fourni"}), 400)
    if not fichier.filename.lower().endswith(_XLSX_EXT):
        return None, (jsonify({"error": "Le fichier doit être au format .xlsx"}), 400)
    return fichier.read(), None


@bp.post("/vehicules")
@role_required(RoleUser.ADMIN)
def importer_vehicules():
    data, err = _fichier_xlsx()
    if err:
        return err
    resultat = import_vehicules(data)
    if "error" in resultat:
        return jsonify(resultat), 400
    return jsonify(resultat)


@bp.post("/clients")
@role_required(RoleUser.ADMIN)
def importer_clients():
    data, err = _fichier_xlsx()
    if err:
        return err
    resultat = import_clients(data)
    if "error" in resultat:
        return jsonify(resultat), 400
    return jsonify(resultat)


@bp.get("/modele/<string:quoi>")
@login_required
def modele(quoi):
    generateurs = {"vehicules": modele_vehicules_xlsx, "clients": modele_clients_xlsx}
    if quoi not in generateurs:
        return jsonify({"error": "Modèle inconnu"}), 404
    import io

    return send_file(
        io.BytesIO(generateurs[quoi]()),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"modele-{quoi}.xlsx",
    )
