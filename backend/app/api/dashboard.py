from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services.dashboard_stats import compute_kpis, compute_revenus_par_mois, compute_top_vehicules

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("/kpis")
@login_required
def get_kpis():
    kpis = compute_kpis(date.today())
    return jsonify(
        {
            "taux_occupation": kpis["taux_occupation"],
            "revenus_du_mois": str(kpis["revenus_du_mois"]),
            "vehicules_disponibles": kpis["vehicules_disponibles"],
            "reservations_en_cours": kpis["reservations_en_cours"],
        }
    )


@bp.get("/revenus-par-mois")
@login_required
def get_revenus_par_mois():
    nombre_mois = request.args.get("mois", default=12, type=int) or 12
    nombre_mois = max(1, min(nombre_mois, 36))

    data = compute_revenus_par_mois(date.today(), nombre_mois)
    return jsonify([{"mois": item["mois"], "revenus": str(item["revenus"])} for item in data])


@bp.get("/top-vehicules")
@login_required
def get_top_vehicules():
    limit = request.args.get("limit", default=5, type=int) or 5
    limit = max(1, min(limit, 20))
    return jsonify(compute_top_vehicules(limit))
