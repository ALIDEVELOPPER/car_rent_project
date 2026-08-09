from datetime import date
from decimal import Decimal

import pytest

from app.models import Client, Reservation, Vehicule
from app.models.enums import ModePaiement, StatutPaiement, StatutVehicule
from app.services.invoicing import (
    InvalidPaiementTransitionError,
    apply_paiement_transition,
    create_facture_for_reservation,
    render_facture_pdf,
)


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


def _make_reservation(db, vehicule, client_obj, date_debut=date(2026, 8, 10), date_fin=date(2026, 8, 15)):
    nombre_jours = (date_fin - date_debut).days
    r = Reservation(
        client_id=client_obj.id,
        vehicule_id=vehicule.id,
        date_debut=date_debut,
        date_fin=date_fin,
        prix_jour_applique=vehicule.tarif_jour,
        montant_total=vehicule.tarif_jour * nombre_jours,
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_create_facture_snapshots_montant(db, vehicule, client_obj):
    reservation = _make_reservation(db, vehicule, client_obj)
    facture = create_facture_for_reservation(reservation)
    db.session.commit()

    assert facture.montant == reservation.montant_total
    assert facture.statut_paiement == StatutPaiement.EN_ATTENTE
    assert facture.numero_facture.startswith("FAC-")


def test_create_facture_is_idempotent(db, vehicule, client_obj):
    reservation = _make_reservation(db, vehicule, client_obj)
    facture1 = create_facture_for_reservation(reservation)
    db.session.commit()
    facture2 = create_facture_for_reservation(reservation)
    db.session.commit()

    assert facture1.id == facture2.id


def test_numero_facture_sequential(db, vehicule, client_obj):
    r1 = _make_reservation(db, vehicule, client_obj, date(2026, 8, 10), date(2026, 8, 15))
    f1 = create_facture_for_reservation(r1)
    db.session.commit()

    r2 = _make_reservation(db, vehicule, client_obj, date(2026, 9, 1), date(2026, 9, 5))
    f2 = create_facture_for_reservation(r2)
    db.session.commit()

    assert f1.numero_facture != f2.numero_facture
    n1 = int(f1.numero_facture.rsplit("-", 1)[1])
    n2 = int(f2.numero_facture.rsplit("-", 1)[1])
    assert n2 == n1 + 1


def test_apply_paiement_transition_requires_mode_for_payee(db, vehicule, client_obj):
    reservation = _make_reservation(db, vehicule, client_obj)
    facture = create_facture_for_reservation(reservation)
    db.session.commit()

    with pytest.raises(ValueError):
        apply_paiement_transition(facture, StatutPaiement.PAYEE)


def test_apply_paiement_transition_success(db, vehicule, client_obj):
    reservation = _make_reservation(db, vehicule, client_obj)
    facture = create_facture_for_reservation(reservation)
    db.session.commit()

    apply_paiement_transition(facture, StatutPaiement.PAYEE, ModePaiement.CARTE)
    assert facture.statut_paiement == StatutPaiement.PAYEE
    assert facture.mode_paiement == ModePaiement.CARTE


def test_apply_paiement_transition_invalid_from_annulee(db, vehicule, client_obj):
    reservation = _make_reservation(db, vehicule, client_obj)
    facture = create_facture_for_reservation(reservation)
    db.session.commit()

    apply_paiement_transition(facture, StatutPaiement.ANNULEE)
    with pytest.raises(InvalidPaiementTransitionError):
        apply_paiement_transition(facture, StatutPaiement.PAYEE, ModePaiement.CARTE)


def test_render_facture_pdf_produces_pdf_bytes(app, db, vehicule, client_obj):
    reservation = _make_reservation(db, vehicule, client_obj)
    facture = create_facture_for_reservation(reservation)
    db.session.commit()

    pdf_bytes = render_facture_pdf(facture)
    assert pdf_bytes.startswith(b"%PDF")
