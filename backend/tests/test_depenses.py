import pytest

from app.models import User
from app.models.enums import RoleUser


@pytest.fixture()
def logged_in(client, db):
    u = User(nom="Admin", email="admin@agence.local", role=RoleUser.ADMIN)
    u.set_password("adminpass123")
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"})
    return u


@pytest.fixture()
def vehicule(client, logged_in):
    return client.post(
        "/api/vehicules",
        json={"marque": "Dacia", "modele": "Logan", "immatriculation": "1-A-1",
              "categorie": "berline", "tarif_jour": "250"},
    ).json


def test_depenses_requires_login(client, vehicule):
    client.post("/api/auth/logout")
    assert client.get(f"/api/vehicules/{vehicule['id']}/depenses").status_code == 401


def test_crud_depense(client, vehicule):
    vid = vehicule["id"]
    resp = client.post(
        f"/api/vehicules/{vid}/depenses",
        json={"type": "assurance", "montant": "3200", "date_depense": "2026-01-15", "note": "annuelle"},
    )
    assert resp.status_code == 201
    dep_id = resp.json["id"]
    assert resp.json["montant"] == "3200.00"

    assert len(client.get(f"/api/vehicules/{vid}/depenses").json) == 1

    resp = client.put(f"/api/depenses/{dep_id}", json={"montant": "3000"})
    assert resp.status_code == 200
    assert resp.json["montant"] == "3000.00"

    assert client.delete(f"/api/depenses/{dep_id}").status_code == 204
    assert client.get(f"/api/vehicules/{vid}/depenses").json == []


def test_depense_validation(client, vehicule):
    vid = vehicule["id"]
    assert client.post(f"/api/vehicules/{vid}/depenses", json={"type": "x", "montant": "1", "date_depense": "2026-01-01"}).status_code == 400
    assert client.post(f"/api/vehicules/{vid}/depenses", json={"type": "autre", "montant": "-5", "date_depense": "2026-01-01"}).status_code == 400
    assert client.post(f"/api/vehicules/{vid}/depenses", json={"type": "autre", "montant": "5"}).status_code == 400


def test_depense_unknown_vehicule(client, logged_in):
    assert client.get("/api/vehicules/9999/depenses").status_code == 404


def test_reservation_source(client, logged_in, db):
    from decimal import Decimal

    from app.models import Client, Vehicule
    from app.models.enums import StatutVehicule

    c = Client(nom="A", prenom="B", telephone="06")
    v = Vehicule(marque="Kia", modele="Rio", immatriculation="2-B-2", categorie="x",
                 tarif_jour=Decimal("200"), statut=StatutVehicule.DISPONIBLE)
    db.session.add_all([c, v])
    db.session.commit()

    resp = client.post("/api/reservations", json={
        "client_id": c.id, "vehicule_id": v.id,
        "date_debut": "2026-08-10", "date_fin": "2026-08-12", "source": "whatsapp",
    })
    assert resp.status_code == 201
    assert resp.json["source"] == "whatsapp"

    resp = client.put(f"/api/reservations/{resp.json['id']}", json={"source": "partenaire"})
    assert resp.json["source"] == "partenaire"

    resp = client.put(f"/api/reservations/{resp.json['id']}", json={"source": "n'importe quoi"})
    assert resp.status_code == 400
