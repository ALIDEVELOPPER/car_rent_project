from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import Client, Facture, Reservation, Vehicule
from app.models.enums import StatutPaiement, StatutReservation, StatutVehicule
from app.services.dashboard_stats import (
    compute_kpis,
    compute_revenus_par_mois,
    compute_revenus_periode,
    compute_taux_occupation,
    compute_top_vehicules,
    count_reservations_en_cours,
    count_vehicules_disponibles,
)


@pytest.fixture()
def client_obj(db):
    c = Client(nom="Alami", prenom="Yassine", telephone="0600000000")
    db.session.add(c)
    db.session.commit()
    return c


def _make_vehicule(db, immatriculation, statut, tarif=Decimal("300")):
    v = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation=immatriculation,
        categorie="citadine",
        tarif_jour=tarif,
        statut=statut,
    )
    db.session.add(v)
    db.session.commit()
    return v


def _make_reservation(db, vehicule, client_obj, date_debut, date_fin, statut):
    r = Reservation(
        client_id=client_obj.id,
        vehicule_id=vehicule.id,
        date_debut=date_debut,
        date_fin=date_fin,
        statut=statut,
        prix_jour_applique=vehicule.tarif_jour,
        montant_total=vehicule.tarif_jour,
    )
    db.session.add(r)
    db.session.commit()
    return r


def _make_facture(db, reservation, montant, statut_paiement, date_emission):
    f = Facture(
        reservation_id=reservation.id,
        numero_facture=f"FAC-TEST-{reservation.id}",
        date_emission=date_emission,
        montant=montant,
        statut_paiement=statut_paiement,
    )
    db.session.add(f)
    db.session.commit()
    return f


def test_taux_occupation_excludes_hors_service(db):
    _make_vehicule(db, "1-A-1", StatutVehicule.DISPONIBLE)
    _make_vehicule(db, "2-A-2", StatutVehicule.LOUE)
    _make_vehicule(db, "3-A-3", StatutVehicule.HORS_SERVICE)

    assert compute_taux_occupation() == 50.0


def test_taux_occupation_zero_when_no_active_vehicules(db):
    _make_vehicule(db, "1-A-1", StatutVehicule.HORS_SERVICE)
    assert compute_taux_occupation() == 0.0


def test_count_vehicules_disponibles(db):
    _make_vehicule(db, "1-A-1", StatutVehicule.DISPONIBLE)
    _make_vehicule(db, "2-A-2", StatutVehicule.LOUE)
    assert count_vehicules_disponibles() == 1


def test_count_reservations_en_cours(db, client_obj):
    v = _make_vehicule(db, "1-A-1", StatutVehicule.LOUE)
    _make_reservation(db, v, client_obj, date(2026, 8, 1), date(2026, 8, 5), StatutReservation.EN_COURS)
    _make_reservation(db, v, client_obj, date(2026, 9, 1), date(2026, 9, 5), StatutReservation.EN_ATTENTE)
    assert count_reservations_en_cours() == 1


def test_revenus_periode_sums_only_paid_factures_in_range(db, client_obj):
    v = _make_vehicule(db, "1-A-1", StatutVehicule.DISPONIBLE)
    r1 = _make_reservation(db, v, client_obj, date(2026, 8, 1), date(2026, 8, 5), StatutReservation.TERMINEE)
    r2 = _make_reservation(db, v, client_obj, date(2026, 8, 10), date(2026, 8, 15), StatutReservation.TERMINEE)
    r3 = _make_reservation(db, v, client_obj, date(2026, 9, 1), date(2026, 9, 5), StatutReservation.TERMINEE)

    _make_facture(db, r1, Decimal("1000"), StatutPaiement.PAYEE, datetime(2026, 8, 3, tzinfo=UTC))
    _make_facture(db, r2, Decimal("500"), StatutPaiement.EN_ATTENTE, datetime(2026, 8, 12, tzinfo=UTC))
    _make_facture(db, r3, Decimal("2000"), StatutPaiement.PAYEE, datetime(2026, 9, 2, tzinfo=UTC))

    total = compute_revenus_periode(date(2026, 8, 1), date(2026, 9, 1))
    assert total == Decimal("1000")


def test_revenus_par_mois_fills_empty_months(db):
    resultats = compute_revenus_par_mois(date(2026, 3, 15), nombre_mois=3)
    assert [r["mois"] for r in resultats] == ["2026-01", "2026-02", "2026-03"]
    assert all(r["revenus"] == Decimal("0") for r in resultats)


def test_top_vehicules_excludes_cancelled(db, client_obj):
    v1 = _make_vehicule(db, "1-A-1", StatutVehicule.DISPONIBLE)
    v2 = _make_vehicule(db, "2-A-2", StatutVehicule.DISPONIBLE)

    _make_reservation(db, v1, client_obj, date(2026, 8, 1), date(2026, 8, 5), StatutReservation.TERMINEE)
    _make_reservation(db, v1, client_obj, date(2026, 8, 10), date(2026, 8, 15), StatutReservation.TERMINEE)
    _make_reservation(db, v1, client_obj, date(2026, 8, 20), date(2026, 8, 25), StatutReservation.ANNULEE)
    _make_reservation(db, v2, client_obj, date(2026, 9, 1), date(2026, 9, 5), StatutReservation.TERMINEE)

    top = compute_top_vehicules(limit=5)
    assert top[0]["vehicule_id"] == v1.id
    assert top[0]["nombre_reservations"] == 2
    assert top[1]["vehicule_id"] == v2.id
    assert top[1]["nombre_reservations"] == 1


def test_compute_kpis_shape(db):
    kpis = compute_kpis(date(2026, 8, 9))
    assert set(kpis.keys()) == {
        "taux_occupation",
        "revenus_du_mois",
        "vehicules_disponibles",
        "reservations_en_cours",
    }
