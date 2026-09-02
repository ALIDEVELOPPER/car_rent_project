from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services.dashboard_stats import (
    compute_agenda_jour,
    compute_cautions_a_restituer,
    compute_echeances,
    compute_flotte,
    compute_impayes,
    compute_kpis,
    compute_prochains_jours,
    compute_revenus_du_mois,
    compute_revenus_mois_precedent,
    compute_revenus_par_mois,
    compute_top_vehicules,
)

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("")
@login_required
def get_dashboard():
    """Vue opérationnelle : ce qu'une agence regarde chaque jour."""
    today = date.today()
    agenda = compute_agenda_jour(today)
    impayes = compute_impayes()
    revenus_mois = compute_revenus_du_mois(today)
    revenus_prec = compute_revenus_mois_precedent(today)
    variation = None
    if revenus_prec > 0:
        variation = round(float((revenus_mois - revenus_prec) / revenus_prec * 100), 1)

    return jsonify(
        {
            "date": today.isoformat(),
            "agenda": agenda,
            "impayes": {"total": str(impayes["total"]), "nombre": impayes["nombre"]},
            "revenus": {
                "mois": str(revenus_mois),
                "mois_precedent": str(revenus_prec),
                "variation_pct": variation,
            },
            "flotte": compute_flotte(),
            "echeances": compute_echeances(today, 30),
            "cautions_a_restituer": compute_cautions_a_restituer(),
            "prochains_jours": compute_prochains_jours(today, 7),
        }
    )


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
