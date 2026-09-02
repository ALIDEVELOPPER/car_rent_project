from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Client, DepenseVehicule, Facture, Reservation, Vehicule
from app.models.enums import (
    SourceReservation,
    StatutCaution,
    StatutPaiement,
    StatutReservation,
    StatutVehicule,
    TypeDepense,
)


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


def compute_revenus_mois_precedent(reference_date: date) -> Decimal:
    debut_mois = reference_date.replace(day=1)
    if debut_mois.month == 1:
        debut_precedent = date(debut_mois.year - 1, 12, 1)
    else:
        debut_precedent = date(debut_mois.year, debut_mois.month - 1, 1)
    return compute_revenus_periode(debut_precedent, debut_mois)


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


ECHEANCE_CHAMPS = [
    ("assurance", "assurance_expire_le"),
    ("visite_technique", "visite_technique_expire_le"),
    ("vignette", "vignette_expire_le"),
    ("vidange", "prochaine_vidange_le"),
]


def compute_echeances(reference_date: date, horizon_jours: int = 30) -> list[dict]:
    """Échéances administratives des véhicules déjà passées ou à moins de
    `horizon_jours`, triées de la plus urgente à la moins urgente."""
    vehicules = db.session.execute(
        db.select(Vehicule).filter(Vehicule.statut != StatutVehicule.HORS_SERVICE)
    ).scalars().all()

    limite = reference_date + timedelta(days=horizon_jours)
    resultats = []
    for v in vehicules:
        for type_, champ in ECHEANCE_CHAMPS:
            echeance = getattr(v, champ)
            if echeance is None or echeance > limite:
                continue
            jours = (echeance - reference_date).days
            resultats.append(
                {
                    "vehicule_id": v.id,
                    "vehicule": f"{v.marque} {v.modele}",
                    "immatriculation": v.immatriculation,
                    "type": type_,
                    "date": echeance.isoformat(),
                    "jours_restants": jours,
                    "en_retard": jours < 0,
                }
            )
    resultats.sort(key=lambda e: e["jours_restants"])
    return resultats


def _douze_mois_avant(reference_date: date) -> date:
    return date(reference_date.year - 1, reference_date.month, 1)


def compute_indicateurs_cles(reference_date: date) -> dict:
    """Indicateurs de pilotage : panier moyen, durée moyenne, activité du mois,
    taux de recouvrement — sur les 12 derniers mois glissants."""
    debut_12m = _douze_mois_avant(reference_date)
    debut_mois = reference_date.replace(day=1)

    locations = db.session.execute(
        db.select(
            Reservation.date_debut, Reservation.date_fin, Reservation.montant_total
        ).filter(
            Reservation.statut != StatutReservation.ANNULEE,
            Reservation.date_debut >= debut_12m,
        )
    ).all()
    nb = len(locations)
    panier_moyen = (
        (sum((row.montant_total for row in locations), Decimal("0")) / nb) if nb else Decimal("0")
    )
    duree_moyenne = (
        sum((row.date_fin - row.date_debut).days for row in locations) / nb if nb else 0
    )

    locations_mois = db.session.execute(
        db.select(db.func.count(Reservation.id)).filter(
            Reservation.statut != StatutReservation.ANNULEE,
            Reservation.date_debut >= debut_mois,
        )
    ).scalar_one()

    nouveaux_clients_mois = db.session.execute(
        db.select(db.func.count(Client.id)).filter(
            Client.created_at >= _to_datetime_utc(debut_mois)
        )
    ).scalar_one()

    facture_total = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Facture.montant), 0)).filter(
            Facture.statut_paiement != StatutPaiement.ANNULEE,
            Facture.date_emission >= _to_datetime_utc(debut_12m),
        )
    ).scalar_one()
    encaisse_total = db.session.execute(
        db.select(db.func.coalesce(db.func.sum(Facture.montant), 0)).filter(
            Facture.statut_paiement == StatutPaiement.PAYEE,
            Facture.date_emission >= _to_datetime_utc(debut_12m),
        )
    ).scalar_one()
    taux_recouvrement = (
        round(float(encaisse_total) / float(facture_total) * 100, 1)
        if facture_total
        else None
    )

    return {
        "panier_moyen": str(Decimal(panier_moyen).quantize(Decimal("0.01"))),
        "duree_moyenne_jours": round(float(duree_moyenne), 1),
        "locations_mois": locations_mois,
        "nouveaux_clients_mois": nouveaux_clients_mois,
        "taux_recouvrement": taux_recouvrement,
        "nb_locations_12m": nb,
    }


def compute_rentabilite_vehicules(reference_date: date, limit: int = 6) -> list[dict]:
    """Rentabilité par véhicule sur les 12 derniers mois : CA facturé,
    charges d'exploitation (hors achat) et marge nette. Trié par marge."""
    debut = _douze_mois_avant(reference_date)
    debut_dt = _to_datetime_utc(debut)

    ca_rows = db.session.execute(
        db.select(
            Vehicule.id,
            Vehicule.marque,
            Vehicule.modele,
            Vehicule.immatriculation,
            db.func.coalesce(db.func.sum(Facture.montant), 0),
            db.func.count(Facture.id),
        )
        .join(Reservation, Reservation.vehicule_id == Vehicule.id)
        .join(Facture, Facture.reservation_id == Reservation.id)
        .filter(
            Facture.statut_paiement != StatutPaiement.ANNULEE,
            Facture.date_emission >= debut_dt,
        )
        .group_by(Vehicule.id)
    ).all()

    charges_rows = db.session.execute(
        db.select(
            DepenseVehicule.vehicule_id,
            db.func.coalesce(db.func.sum(DepenseVehicule.montant), 0),
        )
        .filter(
            DepenseVehicule.type != TypeDepense.ACHAT,
            DepenseVehicule.date_depense >= debut,
        )
        .group_by(DepenseVehicule.vehicule_id)
    ).all()
    charges_par_vehicule = {vid: montant for vid, montant in charges_rows}

    resultats = []
    for vid, marque, modele, immat, ca, nb in ca_rows:
        charges = charges_par_vehicule.get(vid, 0)
        resultats.append(
            {
                "vehicule_id": vid,
                "vehicule": f"{marque} {modele}",
                "immatriculation": immat,
                "ca": str(Decimal(ca)),
                "charges": str(Decimal(charges)),
                "marge": str(Decimal(ca) - Decimal(charges)),
                "nb_locations": nb,
            }
        )
    resultats.sort(key=lambda r: Decimal(r["marge"]), reverse=True)
    return resultats[:limit]


def compute_sources_acquisition(reference_date: date, horizon_jours: int = 90) -> list[dict]:
    """Répartition des réservations par canal d'acquisition sur la période récente."""
    debut = reference_date - timedelta(days=horizon_jours)
    rows = db.session.execute(
        db.select(Reservation.source, db.func.count(Reservation.id))
        .filter(
            Reservation.statut != StatutReservation.ANNULEE,
            Reservation.date_debut >= debut,
        )
        .group_by(Reservation.source)
    ).all()
    total = sum(n for _, n in rows)
    resultats = [
        {
            "source": source.value if source is not None else "agence",
            "nombre": n,
            "pct": round(n / total * 100) if total else 0,
        }
        for source, n in rows
    ]
    # fusionne les lignes "agence" (source explicite + valeurs nulles)
    fusion: dict[str, dict] = {}
    for item in resultats:
        cle = item["source"]
        if cle in fusion:
            fusion[cle]["nombre"] += item["nombre"]
            fusion[cle]["pct"] += item["pct"]
        else:
            fusion[cle] = item
    return sorted(fusion.values(), key=lambda i: i["nombre"], reverse=True)


def compute_cautions_a_restituer() -> list[dict]:
    """Réservations terminées dont la caution a été encaissée mais pas encore
    rendue au client."""
    reservations = db.session.execute(
        db.select(Reservation)
        .join(Client, Client.id == Reservation.client_id)
        .filter(
            Reservation.statut == StatutReservation.TERMINEE,
            Reservation.caution > 0,
            Reservation.caution_statut == StatutCaution.RECUE,
        )
        .order_by(Reservation.date_fin)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "client": f"{r.client.prenom} {r.client.nom}",
            "vehicule": f"{r.vehicule.marque} {r.vehicule.modele}",
            "montant": str(r.caution),
            "date_fin": r.date_fin.isoformat(),
        }
        for r in reservations
    ]


def compute_flotte() -> dict:
    rows = db.session.execute(
        db.select(Vehicule.statut, db.func.count()).group_by(Vehicule.statut)
    ).all()
    counts = {s.value: 0 for s in StatutVehicule}
    for statut, n in rows:
        counts[statut.value] = n
    counts["total"] = sum(v for k, v in counts.items() if k != "total")
    return counts


def compute_impayes() -> dict:
    row = db.session.execute(
        db.select(
            db.func.coalesce(db.func.sum(Facture.montant), 0),
            db.func.count(Facture.id),
        ).filter(Facture.statut_paiement == StatutPaiement.EN_ATTENTE)
    ).one()
    return {"total": Decimal(row[0]), "nombre": row[1]}


def _serialize_ligne_agenda(reservation: Reservation, reference_date: date, heure: str | None = None) -> dict:
    client = reservation.client
    vehicule = reservation.vehicule
    retard_jours = max(0, (reference_date - reservation.date_fin).days)
    return {
        "id": reservation.id,
        "client": f"{client.prenom} {client.nom}",
        "vehicule": f"{vehicule.marque} {vehicule.modele}",
        "immatriculation": vehicule.immatriculation,
        "date_debut": reservation.date_debut.isoformat(),
        "date_fin": reservation.date_fin.isoformat(),
        "heure": heure,
        "statut": reservation.statut.value,
        "retard_jours": retard_jours,
    }


def compute_agenda_jour(reference_date: date) -> dict:
    def _q():
        return (
            db.select(Reservation)
            .join(Client, Client.id == Reservation.client_id)
            .join(Vehicule, Vehicule.id == Reservation.vehicule_id)
        )

    departs = db.session.execute(
        _q().filter(
            Reservation.date_debut == reference_date,
            Reservation.statut.in_([StatutReservation.EN_ATTENTE, StatutReservation.CONFIRMEE]),
        ).order_by(Reservation.id)
    ).scalars().all()

    retours = db.session.execute(
        _q().filter(
            Reservation.date_fin == reference_date,
            Reservation.statut == StatutReservation.EN_COURS,
        ).order_by(Reservation.id)
    ).scalars().all()

    retards = db.session.execute(
        _q().filter(
            Reservation.date_fin < reference_date,
            Reservation.statut == StatutReservation.EN_COURS,
        ).order_by(Reservation.date_fin)
    ).scalars().all()

    return {
        "departs": [_serialize_ligne_agenda(r, reference_date, r.heure_debut) for r in departs],
        "retours": [_serialize_ligne_agenda(r, reference_date, r.heure_fin) for r in retours],
        "retards": [_serialize_ligne_agenda(r, reference_date, r.heure_fin) for r in retards],
    }


def compute_prochains_jours(reference_date: date, jours: int = 7) -> list[dict]:
    fin = reference_date + timedelta(days=jours)
    reservations = db.session.execute(
        db.select(Reservation)
        .join(Client, Client.id == Reservation.client_id)
        .join(Vehicule, Vehicule.id == Reservation.vehicule_id)
        .filter(
            Reservation.date_debut >= reference_date,
            Reservation.date_debut < fin,
            Reservation.statut.in_([StatutReservation.EN_ATTENTE, StatutReservation.CONFIRMEE]),
        )
        .order_by(Reservation.date_debut, Reservation.id)
    ).scalars().all()

    par_jour: dict[str, list] = {}
    for r in reservations:
        nb_jours = (r.date_fin - r.date_debut).days
        par_jour.setdefault(r.date_debut.isoformat(), []).append(
            {
                "id": r.id,
                "vehicule": f"{r.vehicule.marque} {r.vehicule.modele}",
                "client": f"{r.client.prenom} {r.client.nom}",
                "nb_jours": nb_jours,
            }
        )

    return [
        {"date": (reference_date + timedelta(days=i)).isoformat(),
         "reservations": par_jour.get((reference_date + timedelta(days=i)).isoformat(), [])}
        for i in range(jours)
    ]


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
