from datetime import date
from decimal import Decimal

import pytest

from app.models import Client, Reservation, Vehicule
from app.models.enums import StatutReservation, StatutVehicule
from app.services.availability import is_vehicule_available


@pytest.fixture()
def vehicule(db):
    v = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation="1-A-1",
        categorie="citadine",
        tarif_jour=Decimal("300"),
        statut=StatutVehicule.DISPONIBLE,
    )
    db.session.add(v)
    db.session.commit()
    return v


@pytest.fixture()
def client_obj(db):
    c = Client(nom="Alami", prenom="Yassine", telephone="0600000000")
    db.session.add(c)
    db.session.commit()
    return c


def _make_reservation(db, vehicule, client_obj, date_debut, date_fin, statut=StatutReservation.CONFIRMEE):
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


def test_available_when_no_reservations(db, vehicule):
    assert is_vehicule_available(vehicule.id, date(2026, 8, 10), date(2026, 8, 15))


def test_unavailable_on_exact_overlap(db, vehicule, client_obj):
    _make_reservation(db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15))
    assert not is_vehicule_available(vehicule.id, date(2026, 8, 10), date(2026, 8, 15))


def test_unavailable_on_partial_overlap(db, vehicule, client_obj):
    _make_reservation(db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15))
    assert not is_vehicule_available(vehicule.id, date(2026, 8, 12), date(2026, 8, 20))
    assert not is_vehicule_available(vehicule.id, date(2026, 8, 5), date(2026, 8, 11))


def test_available_same_day_turnover(db, vehicule, client_obj):
    _make_reservation(db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15))
    assert is_vehicule_available(vehicule.id, date(2026, 8, 15), date(2026, 8, 20))
    assert is_vehicule_available(vehicule.id, date(2026, 8, 1), date(2026, 8, 10))


def test_cancelled_reservation_does_not_block(db, vehicule, client_obj):
    _make_reservation(
        db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15), statut=StatutReservation.ANNULEE
    )
    assert is_vehicule_available(vehicule.id, date(2026, 8, 10), date(2026, 8, 15))


def test_exclude_reservation_id_allows_self_overlap(db, vehicule, client_obj):
    r = _make_reservation(db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15))
    assert is_vehicule_available(
        vehicule.id, date(2026, 8, 10), date(2026, 8, 15), exclude_reservation_id=r.id
    )


def test_different_vehicule_not_affected(db, vehicule, client_obj):
    other_vehicule = Vehicule(
        marque="Dacia",
        modele="Logan",
        immatriculation="2-B-2",
        categorie="berline",
        tarif_jour=Decimal("250"),
        statut=StatutVehicule.DISPONIBLE,
    )
    db.session.add(other_vehicule)
    db.session.commit()

    _make_reservation(db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15))
    assert is_vehicule_available(other_vehicule.id, date(2026, 8, 10), date(2026, 8, 15))
