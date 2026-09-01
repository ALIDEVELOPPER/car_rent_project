from decimal import Decimal

import pytest

from app.models import Client, User, Vehicule
from app.models.enums import RoleUser, StatutVehicule


@pytest.fixture()
def logged_in_employe(client, db):
    employe = User(nom="Employe", email="employe@agence.local", role=RoleUser.EMPLOYE)
    employe.set_password("employepass123")
    db.session.add(employe)
    db.session.commit()
    client.post(
        "/api/auth/login", json={"email": "employe@agence.local", "mot_de_passe": "employepass123"}
    )
    return employe


@pytest.fixture()
def client_obj(db):
    c = Client(nom="Alami", prenom="Yassine", telephone="0600000000")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def vehicule(db):
    v = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation="1-A-1",
        categorie="citadine",
        tarif_jour=Decimal("300.00"),
        statut=StatutVehicule.DISPONIBLE,
    )
    db.session.add(v)
    db.session.commit()
    return v


def _create_reservation(client, client_obj, vehicule, **overrides):
    payload = {
        "client_id": client_obj.id,
        "vehicule_id": vehicule.id,
        "date_debut": "2026-08-10",
        "date_fin": "2026-08-15",
    }
    payload.update(overrides)
    return client.post("/api/reservations", json=payload)


def test_create_reservation_requires_login(client, client_obj, vehicule):
    resp = _create_reservation(client, client_obj, vehicule)
    assert resp.status_code == 401


def test_create_reservation_success_computes_price(client, logged_in_employe, client_obj, vehicule):
    resp = _create_reservation(client, client_obj, vehicule)
    assert resp.status_code == 201
    assert resp.json["montant_total"] == "1500.00"
    assert resp.json["prix_jour_applique"] == "300.00"
    assert resp.json["statut"] == "en_attente"
    assert resp.json["caution"] == "0.00"


def test_create_reservation_with_caution_and_lieu(client, logged_in_employe, client_obj, vehicule):
    resp = _create_reservation(
        client, client_obj, vehicule, caution="2500", lieu_prise_en_charge="Aéroport"
    )
    assert resp.status_code == 201
    assert resp.json["caution"] == "2500.00"
    assert resp.json["lieu_prise_en_charge"] == "Aéroport"


def test_create_reservation_negative_caution_rejected(client, logged_in_employe, client_obj, vehicule):
    resp = _create_reservation(client, client_obj, vehicule, caution="-10")
    assert resp.status_code == 400


def test_contrat_pdf_download(client, logged_in_employe, client_obj, vehicule):
    created = _create_reservation(client, client_obj, vehicule).json
    resp = client.get(f"/api/reservations/{created['id']}/contrat/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_contrat_pdf_arabic(client, logged_in_employe, client_obj, vehicule, db):
    from app.services.agence import get_or_create_agence

    agence = get_or_create_agence()
    agence.langue = "ar"
    db.session.commit()

    created = _create_reservation(client, client_obj, vehicule).json
    resp = client.get(f"/api/reservations/{created['id']}/contrat/pdf")
    assert resp.status_code == 200
    assert resp.data[:5] == b"%PDF-"
    assert len(resp.data) > 2000


def test_contrat_pdf_requires_login(client):
    resp = client.get("/api/reservations/1/contrat/pdf")
    assert resp.status_code == 401


def test_contrat_pdf_404_unknown(client, logged_in_employe):
    resp = client.get("/api/reservations/9999/contrat/pdf")
    assert resp.status_code == 404


def test_contrat_pdf_409_for_cancelled(client, logged_in_employe, client_obj, vehicule):
    created = _create_reservation(client, client_obj, vehicule).json
    client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "annulee"})
    resp = client.get(f"/api/reservations/{created['id']}/contrat/pdf")
    assert resp.status_code == 409


@pytest.mark.parametrize("statut", [StatutVehicule.MAINTENANCE, StatutVehicule.HORS_SERVICE])
def test_create_reservation_refuse_vehicule_indisponible(
    client, logged_in_employe, client_obj, vehicule, db, statut
):
    vehicule.statut = statut
    db.session.commit()

    resp = _create_reservation(client, client_obj, vehicule)
    assert resp.status_code == 409
    assert "maintenance" in resp.json["error"].lower() or "hors service" in resp.json["error"].lower()


@pytest.mark.parametrize("statut", [StatutVehicule.MAINTENANCE, StatutVehicule.HORS_SERVICE])
def test_disponibilite_endpoint_vehicule_hors_service(
    client, logged_in_employe, vehicule, db, statut
):
    vehicule.statut = statut
    db.session.commit()

    resp = client.get(
        f"/api/vehicules/{vehicule.id}/disponibilite?date_debut=2026-08-10&date_fin=2026-08-15"
    )
    assert resp.status_code == 200
    assert resp.json["disponible"] is False
    assert resp.json["raison"] == "hors_service"


def test_create_reservation_unknown_client(client, logged_in_employe, vehicule):
    resp = client.post(
        "/api/reservations",
        json={
            "client_id": 9999,
            "vehicule_id": vehicule.id,
            "date_debut": "2026-08-10",
            "date_fin": "2026-08-15",
        },
    )
    assert resp.status_code == 404


def test_create_reservation_unknown_vehicule(client, logged_in_employe, client_obj):
    resp = client.post(
        "/api/reservations",
        json={
            "client_id": client_obj.id,
            "vehicule_id": 9999,
            "date_debut": "2026-08-10",
            "date_fin": "2026-08-15",
        },
    )
    assert resp.status_code == 404


def test_create_reservation_invalid_date_range(client, logged_in_employe, client_obj, vehicule):
    resp = _create_reservation(client, client_obj, vehicule, date_debut="2026-08-15", date_fin="2026-08-10")
    assert resp.status_code == 400


def test_create_reservation_montant_total_ignores_client_input(
    client, logged_in_employe, client_obj, vehicule
):
    resp = _create_reservation(client, client_obj, vehicule, montant_total="1.00")
    assert resp.status_code == 201
    assert resp.json["montant_total"] == "1500.00"


def test_create_reservation_conflict_on_overlap(client, logged_in_employe, client_obj, vehicule):
    _create_reservation(client, client_obj, vehicule)
    resp = _create_reservation(client, client_obj, vehicule, date_debut="2026-08-12", date_fin="2026-08-18")
    assert resp.status_code == 409


def test_create_reservation_allows_same_day_turnover(client, logged_in_employe, client_obj, vehicule):
    _create_reservation(client, client_obj, vehicule)
    resp = _create_reservation(client, client_obj, vehicule, date_debut="2026-08-15", date_fin="2026-08-20")
    assert resp.status_code == 201


def test_get_unknown_reservation_returns_404(client, logged_in_employe):
    resp = client.get("/api/reservations/9999")
    assert resp.status_code == 404


def test_update_reservation_dates_recomputes_price_at_locked_rate(
    client, logged_in_employe, client_obj, vehicule
):
    created = _create_reservation(client, client_obj, vehicule).json

    resp = client.put(
        f"/api/reservations/{created['id']}", json={"date_debut": "2026-08-10", "date_fin": "2026-08-20"}
    )
    assert resp.status_code == 200
    assert resp.json["prix_jour_applique"] == "300.00"
    assert resp.json["montant_total"] == "3000.00"


def test_update_reservation_date_conflict(client, logged_in_employe, client_obj, vehicule):
    created = _create_reservation(client, client_obj, vehicule).json
    _create_reservation(client, client_obj, vehicule, date_debut="2026-09-01", date_fin="2026-09-05")

    resp = client.put(
        f"/api/reservations/{created['id']}", json={"date_debut": "2026-09-02", "date_fin": "2026-09-06"}
    )
    assert resp.status_code == 409


def test_change_statut_full_lifecycle_updates_vehicule(
    client, logged_in_employe, client_obj, vehicule
):
    created = _create_reservation(client, client_obj, vehicule).json

    resp = client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "confirmee"})
    assert resp.status_code == 200

    resp = client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "en_cours"})
    assert resp.status_code == 200

    resp = client.get(f"/api/vehicules/{vehicule.id}")
    assert resp.json["statut"] == "loue"

    resp = client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "terminee"})
    assert resp.status_code == 200

    resp = client.get(f"/api/vehicules/{vehicule.id}")
    assert resp.json["statut"] == "disponible"


def test_change_statut_invalid_transition_rejected(client, logged_in_employe, client_obj, vehicule):
    created = _create_reservation(client, client_obj, vehicule).json

    resp = client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "terminee"})
    assert resp.status_code == 409


def test_update_reservation_blocked_after_terminee(client, logged_in_employe, client_obj, vehicule):
    created = _create_reservation(client, client_obj, vehicule).json
    client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "confirmee"})
    client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "en_cours"})
    client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "terminee"})

    resp = client.put(f"/api/reservations/{created['id']}", json={"notes": "test"})
    assert resp.status_code == 409


def test_cancelled_reservation_frees_the_dates(client, logged_in_employe, client_obj, vehicule):
    created = _create_reservation(client, client_obj, vehicule).json
    client.patch(f"/api/reservations/{created['id']}/statut", json={"statut": "annulee"})

    resp = _create_reservation(client, client_obj, vehicule)
    assert resp.status_code == 201


def test_disponibilite_endpoint(client, logged_in_employe, client_obj, vehicule):
    resp = client.get(
        f"/api/vehicules/{vehicule.id}/disponibilite?date_debut=2026-08-10&date_fin=2026-08-15"
    )
    assert resp.status_code == 200
    assert resp.json["disponible"] is True

    _create_reservation(client, client_obj, vehicule)

    resp = client.get(
        f"/api/vehicules/{vehicule.id}/disponibilite?date_debut=2026-08-10&date_fin=2026-08-15"
    )
    assert resp.json["disponible"] is False
