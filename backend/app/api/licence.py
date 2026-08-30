from flask import Blueprint, current_app, jsonify, request

from app.services import licence as licence_service

bp = Blueprint("licence", __name__, url_prefix="/api/licence")


@bp.get("/status")
def status():
    force = request.args.get("force") == "1"
    state = licence_service.get_state(current_app.config["LICENCE_SERVER_URL"], force=force)

    cache = state.get("cache") or {}
    return jsonify(
        {
            "activated": state["activated"],
            "blocked": state["blocked"],
            "reason": state["reason"],
            "statut": cache.get("statut"),
            "jours_essai_restants": cache.get("jours_essai_restants"),
            "essai_expire_le": cache.get("essai_expire_le"),
            "bloque_le": cache.get("bloque_le"),
            "contact_email": current_app.config["CONTACT_EMAIL"],
            "contact_phone": current_app.config["CONTACT_PHONE"],
        }
    )
