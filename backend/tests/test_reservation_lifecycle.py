from datetime import date
from decimal import Decimal

import pytest

from app.models import Client, Reservation, Vehicule
from app.models.enums import StatutReservation, StatutVehicule
from app.services.reservation_lifecycle import InvalidTransitionError, apply_statut_transition


@pytest.fixture()
def vehicule(db):
    v = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation="1-A-1",
        categorie="citadine",
        tarif_jour=Decimal("300"),
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


@pytest.fixture()
def reservation(db, vehicule, client_obj):
    r = Reservation(
        client_id=client_obj.id,
        vehicule_id=vehicule.id,
        date_debut=date(2026, 8, 10),
        date_fin=date(2026, 8, 15),
        prix_jour_applique=vehicule.tarif_jour,
        montant_total=vehicule.tarif_jour * 5,
        statut=StatutReservation.EN_ATTENTE,
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_en_cours_sets_vehicule_loue(db, reservation, vehicule):
    apply_statut_transition(reservation, StatutReservation.EN_COURS)
    db.session.commit()
    assert vehicule.statut == StatutVehicule.LOUE


def test_terminee_sets_vehicule_disponible(db, reservation, vehicule):
    apply_statut_transition(reservation, StatutReservation.EN_COURS)
    apply_statut_transition(reservation, StatutReservation.TERMINEE)
    db.session.commit()
    assert vehicule.statut == StatutVehicule.DISPONIBLE


def test_annulee_from_en_attente_does_not_touch_disponible_vehicule(db, reservation, vehicule):
    assert vehicule.statut == StatutVehicule.DISPONIBLE
    apply_statut_transition(reservation, StatutReservation.ANNULEE)
    assert vehicule.statut == StatutVehicule.DISPONIBLE


def test_terminee_does_not_override_manual_maintenance(db, reservation, vehicule):
    apply_statut_transition(reservation, StatutReservation.EN_COURS)
    vehicule.statut = StatutVehicule.MAINTENANCE
    apply_statut_transition(reservation, StatutReservation.TERMINEE)
    assert vehicule.statut == StatutVehicule.MAINTENANCE


def test_invalid_transition_terminee_to_en_cours(db, reservation):
    apply_statut_transition(reservation, StatutReservation.EN_COURS)
    apply_statut_transition(reservation, StatutReservation.TERMINEE)
    with pytest.raises(InvalidTransitionError):
        apply_statut_transition(reservation, StatutReservation.EN_COURS)


def test_invalid_transition_confirmee_to_en_attente(db, reservation):
    apply_statut_transition(reservation, StatutReservation.CONFIRMEE)
    with pytest.raises(InvalidTransitionError):
        apply_statut_transition(reservation, StatutReservation.EN_ATTENTE)
