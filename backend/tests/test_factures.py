import pytest

from app.models import User
from app.models.enums import RoleUser


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


def _setup_completed_reservation(client):
    client_resp = client.post(
        "/api/clients", json={"nom": "Alami", "prenom": "Yassine", "telephone": "0600000000"}
    )
    vehicule_resp = client.post(
        "/api/vehicules",
        json={
            "marque": "Renault",
            "modele": "Clio",
            "immatriculation": "1-A-1",
            "categorie": "citadine",
            "tarif_jour": "300.00",
        },
    )

    reservation_resp = client.post(
        "/api/reservations",
        json={
            "client_id": client_resp.json["id"],
            "vehicule_id": vehicule_resp.json["id"],
            "date_debut": "2026-08-10",
            "date_fin": "2026-08-15",
        },
    )
    reservation_id = reservation_resp.json["id"]

    client.patch(f"/api/reservations/{reservation_id}/statut", json={"statut": "confirmee"})
    client.patch(f"/api/reservations/{reservation_id}/statut", json={"statut": "en_cours"})
    resp = client.patch(f"/api/reservations/{reservation_id}/statut", json={"statut": "terminee"})
    return resp.json


def test_facture_created_automatically_on_reservation_termination(client, logged_in_employe):
    reservation = _setup_completed_reservation(client)
    assert reservation["facture_id"] is not None

    resp = client.get(f"/api/factures/{reservation['facture_id']}")
    assert resp.status_code == 200
    assert resp.json["montant"] == "1500.00"
    assert resp.json["statut_paiement"] == "en_attente"
    assert resp.json["client"]["nom"] == "Alami"
    assert resp.json["vehicule"]["immatriculation"] == "1-A-1"


def test_list_factures_includes_client_and_vehicule(client, logged_in_employe):
    _setup_completed_reservation(client)

    resp = client.get("/api/factures")
    assert resp.status_code == 200
    assert resp.json[0]["client"]["nom"] == "Alami"
    assert resp.json[0]["vehicule"]["immatriculation"] == "1-A-1"


def test_list_factures_filter_by_statut(client, logged_in_employe):
    reservation = _setup_completed_reservation(client)

    resp = client.get("/api/factures?statut_paiement=en_attente")
    assert resp.status_code == 200
    assert any(f["id"] == reservation["facture_id"] for f in resp.json)

    resp = client.get("/api/factures?statut_paiement=payee")
    assert resp.status_code == 200
    assert resp.json == []


def test_get_unknown_facture_returns_404(client, logged_in_employe):
    resp = client.get("/api/factures/9999")
    assert resp.status_code == 404


def test_mark_facture_payee_requires_mode_paiement(client, logged_in_employe):
    reservation = _setup_completed_reservation(client)

    resp = client.patch(
        f"/api/factures/{reservation['facture_id']}/statut-paiement", json={"statut_paiement": "payee"}
    )
    assert resp.status_code == 400


def test_mark_facture_payee_success(client, logged_in_employe):
    reservation = _setup_completed_reservation(client)

    resp = client.patch(
        f"/api/factures/{reservation['facture_id']}/statut-paiement",
        json={"statut_paiement": "payee", "mode_paiement": "carte"},
    )
    assert resp.status_code == 200
    assert resp.json["statut_paiement"] == "payee"
    assert resp.json["mode_paiement"] == "carte"


def test_facture_payee_cannot_go_back_to_en_attente(client, logged_in_employe):
    reservation = _setup_completed_reservation(client)
    client.patch(
        f"/api/factures/{reservation['facture_id']}/statut-paiement",
        json={"statut_paiement": "payee", "mode_paiement": "carte"},
    )

    resp = client.patch(
        f"/api/factures/{reservation['facture_id']}/statut-paiement",
        json={"statut_paiement": "en_attente"},
    )
    assert resp.status_code == 409


def test_download_pdf(client, logged_in_employe):
    reservation = _setup_completed_reservation(client)

    resp = client.get(f"/api/factures/{reservation['facture_id']}/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF")


def test_download_pdf_requires_login(client):
    resp = client.get("/api/factures/1/pdf")
    assert resp.status_code == 401
