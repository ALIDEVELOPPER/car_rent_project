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


def test_kpis_requires_login(client):
    resp = client.get("/api/dashboard/kpis")
    assert resp.status_code == 401


def test_kpis_shape(client, logged_in_employe):
    resp = client.get("/api/dashboard/kpis")
    assert resp.status_code == 200
    assert set(resp.json.keys()) == {
        "taux_occupation",
        "revenus_du_mois",
        "vehicules_disponibles",
        "reservations_en_cours",
    }


def test_revenus_par_mois_default_12_months(client, logged_in_employe):
    resp = client.get("/api/dashboard/revenus-par-mois")
    assert resp.status_code == 200
    assert len(resp.json) == 12


def test_revenus_par_mois_custom_range_clamped(client, logged_in_employe):
    resp = client.get("/api/dashboard/revenus-par-mois?mois=100")
    assert resp.status_code == 200
    assert len(resp.json) == 36


def test_top_vehicules_empty_fleet(client, logged_in_employe):
    resp = client.get("/api/dashboard/top-vehicules")
    assert resp.status_code == 200
    assert resp.json == []


def test_top_vehicules_reflects_reservations(client, logged_in_employe):
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
            "tarif_jour": "300",
        },
    )

    client.post(
        "/api/reservations",
        json={
            "client_id": client_resp.json["id"],
            "vehicule_id": vehicule_resp.json["id"],
            "date_debut": "2026-08-10",
            "date_fin": "2026-08-15",
        },
    )

    resp = client.get("/api/dashboard/top-vehicules")
    assert resp.status_code == 200
    assert resp.json[0]["vehicule_id"] == vehicule_resp.json["id"]
    assert resp.json[0]["nombre_reservations"] == 1
