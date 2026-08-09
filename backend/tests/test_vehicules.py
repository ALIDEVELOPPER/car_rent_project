import io
from datetime import date

import pytest

from app.models import Client, Reservation, User, Vehicule
from app.models.enums import RoleUser, StatutVehicule


@pytest.fixture()
def logged_in_admin(client, db):
    admin = User(nom="Admin", email="admin@agence.local", role=RoleUser.ADMIN)
    admin.set_password("adminpass123")
    db.session.add(admin)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"})
    return admin


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


def _create_vehicule(client, **overrides):
    payload = {
        "marque": "Renault",
        "modele": "Clio",
        "immatriculation": "12345-A-6",
        "categorie": "citadine",
        "tarif_jour": "350.00",
    }
    payload.update(overrides)
    resp = client.post("/api/vehicules", json=payload)
    assert resp.status_code == 201
    return resp.json


def test_create_vehicule_requires_login(client):
    resp = client.post(
        "/api/vehicules",
        json={"marque": "Renault", "modele": "Clio", "immatriculation": "1-A-1", "categorie": "citadine", "tarif_jour": "300"},
    )
    assert resp.status_code == 401


def test_create_vehicule_missing_fields(client, logged_in_employe):
    resp = client.post("/api/vehicules", json={"marque": "Renault"})
    assert resp.status_code == 400


def test_create_vehicule_defaults_statut_disponible(client, logged_in_employe):
    created = _create_vehicule(client)
    assert created["statut"] == "disponible"
    assert created["tarif_jour"] == "350.00"


def test_create_vehicule_duplicate_immatriculation_conflict(client, logged_in_employe):
    _create_vehicule(client, immatriculation="99999-B-9")

    resp = client.post(
        "/api/vehicules",
        json={
            "marque": "Dacia",
            "modele": "Logan",
            "immatriculation": "99999-B-9",
            "categorie": "berline",
            "tarif_jour": "250",
        },
    )
    assert resp.status_code == 409


def test_create_vehicule_negative_tarif_rejected(client, logged_in_employe):
    resp = client.post(
        "/api/vehicules",
        json={
            "marque": "Renault",
            "modele": "Clio",
            "immatriculation": "1-A-1",
            "categorie": "citadine",
            "tarif_jour": "-100",
        },
    )
    assert resp.status_code == 400


def test_get_unknown_vehicule_returns_404(client, logged_in_employe):
    resp = client.get("/api/vehicules/9999")
    assert resp.status_code == 404


def test_list_vehicules_filter_by_statut(client, logged_in_employe):
    v1 = _create_vehicule(client, immatriculation="11111-A-1")
    v2 = _create_vehicule(client, immatriculation="22222-A-2")
    client.put(f"/api/vehicules/{v2['id']}", json={"statut": "maintenance"})

    resp = client.get("/api/vehicules?statut=maintenance")
    assert resp.status_code == 200
    assert len(resp.json) == 1
    assert resp.json[0]["id"] == v2["id"]


def test_list_vehicules_invalid_statut_filter(client, logged_in_employe):
    resp = client.get("/api/vehicules?statut=inconnu")
    assert resp.status_code == 400


def test_update_vehicule_tarif_and_statut(client, logged_in_employe):
    created = _create_vehicule(client)

    resp = client.put(
        f"/api/vehicules/{created['id']}", json={"tarif_jour": "400.50", "statut": "maintenance"}
    )
    assert resp.status_code == 200
    assert resp.json["tarif_jour"] == "400.50"
    assert resp.json["statut"] == "maintenance"


def test_update_vehicule_invalid_carburant(client, logged_in_employe):
    created = _create_vehicule(client)

    resp = client.put(f"/api/vehicules/{created['id']}", json={"carburant": "nucleaire"})
    assert resp.status_code == 400


def test_delete_vehicule_requires_admin(client, logged_in_employe):
    created = _create_vehicule(client)

    resp = client.delete(f"/api/vehicules/{created['id']}")
    assert resp.status_code == 403


def test_delete_vehicule_success(client, logged_in_admin):
    created = _create_vehicule(client)

    resp = client.delete(f"/api/vehicules/{created['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/api/vehicules/{created['id']}")
    assert resp.status_code == 404


def test_delete_vehicule_blocked_by_reservations(client, logged_in_admin, db):
    created = _create_vehicule(client)

    client_obj = Client(nom="Alami", prenom="Yassine", telephone="0600000000")
    db.session.add(client_obj)
    db.session.commit()

    vehicule = db.session.get(Vehicule, created["id"])
    reservation = Reservation(
        client_id=client_obj.id,
        vehicule_id=vehicule.id,
        date_debut=date(2026, 8, 10),
        date_fin=date(2026, 8, 15),
        prix_jour_applique=vehicule.tarif_jour,
        montant_total=vehicule.tarif_jour * 5,
    )
    db.session.add(reservation)
    db.session.commit()

    resp = client.delete(f"/api/vehicules/{vehicule.id}")
    assert resp.status_code == 409


def test_upload_photo_success(client, logged_in_employe):
    created = _create_vehicule(client)

    resp = client.post(
        f"/api/vehicules/{created['id']}/photo",
        data={"fichier": (io.BytesIO(b"fake-jpeg-bytes"), "clio.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    url = resp.json["photo_url"]
    assert url.startswith(f"vehicules/{created['id']}/photos/")

    download = client.get(f"/api/uploads/{url}")
    assert download.status_code == 200
    assert download.data == b"fake-jpeg-bytes"


def test_upload_photo_rejects_pdf(client, logged_in_employe):
    created = _create_vehicule(client)

    resp = client.post(
        f"/api/vehicules/{created['id']}/photo",
        data={"fichier": (io.BytesIO(b"%PDF-1.4"), "doc.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
