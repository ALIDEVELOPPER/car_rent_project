import requests
from flask import Blueprint, current_app, jsonify, request

from app.services import licence as licence_service

bp = Blueprint("licence", __name__, url_prefix="/api/licence")


@bp.get("/status")
def status():
    force = request.args.get("force") == "1"
    state = licence_service.get_state(current_app.config["LICENCE_SERVER_URL"], force=force)
    return jsonify(state)


@bp.post("/activate")
def activate():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "Code requis"}), 400

    try:
        result = licence_service.activate(code, current_app.config["LICENCE_SERVER_URL"])
    except licence_service.CodeInvalide as exc:
        return jsonify({"error": str(exc)}), 400
    except requests.RequestException:
        return jsonify({"error": "Impossible de contacter le serveur d'activation. Vérifiez votre connexion internet."}), 502

    return jsonify(result)
