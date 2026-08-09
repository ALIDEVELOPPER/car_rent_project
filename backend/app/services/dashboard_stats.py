from datetime import UTC, date, datetime
from decimal import Decimal

from app.extensions import db
from app.models import Facture, Reservation, Vehicule
from app.models.enums import StatutPaiement, StatutReservation, StatutVehicule


def _to_datetime_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def _next_month(annee: int, mois: int) -> tuple[int, int]:
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def compute_taux_occupation() -> float:
    total_actif = db.session.execute(
        db.select(db.func.count())
        .select_from(Vehicule)
        .filter(Vehicule.statut != StatutVehicule.HORS_SERVICE)
    ).scalar_one()
    if total_actif == 0:
        return 0.0

    loues = db.session.execute(
        db.select(db.func.count())
        .select_from(Vehicule)
        .filter(Vehicule.statut == StatutVehicule.LOUE)
    ).scalar_one()

    return round((loues / total_actif) * 100, 1)


def compute_revenus_periode(date_debut: date, date_fin_exclusive: date) -> Decimal:
    total = db.session.execute(
        db.select(db.func.sum(Facture.montant)).filter(
            Facture.statut_paiement == StatutPaiement.PAYEE,
            Facture.date_emission >= _to_datetime_utc(date_debut),
            Facture.date_emission < _to_datetime_utc(date_fin_exclusive),
        )
    ).scalar_one_or_none()
    return Decimal(total) if total is not None else Decimal("0")


def compute_revenus_du_mois(reference_date: date) -> Decimal:
    debut_mois = reference_date.replace(day=1)
    annee_suivante, mois_suivant = _next_month(reference_date.year, reference_date.month)
    debut_mois_suivant = date(annee_suivante, mois_suivant, 1)
    return compute_revenus_periode(debut_mois, debut_mois_suivant)


def count_vehicules_disponibles() -> int:
    return db.session.execute(
        db.select(db.func.count())
        .select_from(Vehicule)
        .filter(Vehicule.statut == StatutVehicule.DISPONIBLE)
    ).scalar_one()


def count_reservations_en_cours() -> int:
    return db.session.execute(
        db.select(db.func.count())
        .select_from(Reservation)
        .filter(Reservation.statut == StatutReservation.EN_COURS)
    ).scalar_one()


def compute_kpis(reference_date: date) -> dict:
    return {
        "taux_occupation": compute_taux_occupation(),
        "revenus_du_mois": compute_revenus_du_mois(reference_date),
        "vehicules_disponibles": count_vehicules_disponibles(),
        "reservations_en_cours": count_reservations_en_cours(),
    }


def compute_revenus_par_mois(reference_date: date, nombre_mois: int = 12) -> list[dict]:
    mois_liste = []
    annee, mois = reference_date.year, reference_date.month
    for _ in range(nombre_mois):
        mois_liste.append((annee, mois))
        mois -= 1
        if mois == 0:
            mois = 12
            annee -= 1
    mois_liste.reverse()

    resultats = []
    for annee, mois in mois_liste:
        debut = date(annee, mois, 1)
        annee_fin, mois_fin = _next_month(annee, mois)
        fin = date(annee_fin, mois_fin, 1)
        resultats.append({"mois": f"{annee:04d}-{mois:02d}", "revenus": compute_revenus_periode(debut, fin)})
    return resultats


def compute_top_vehicules(limit: int = 5) -> list[dict]:
    nombre = db.func.count(Reservation.id).label("nombre_reservations")
    query = (
        db.select(
            Vehicule.id,
            Vehicule.marque,
            Vehicule.modele,
            Vehicule.immatriculation,
            nombre,
        )
        .join(Reservation, Reservation.vehicule_id == Vehicule.id)
        .filter(Reservation.statut != StatutReservation.ANNULEE)
        .group_by(Vehicule.id)
        .order_by(nombre.desc())
        .limit(limit)
    )
    rows = db.session.execute(query).all()
    return [
        {
            "vehicule_id": row.id,
            "marque": row.marque,
            "modele": row.modele,
            "immatriculation": row.immatriculation,
            "nombre_reservations": row.nombre_reservations,
        }
        for row in rows
    ]
