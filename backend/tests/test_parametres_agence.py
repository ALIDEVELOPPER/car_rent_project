import io

import pytest

from app.models import User
from app.models.enums import RoleUser


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


def test_get_agence_requires_login(client):
    resp = client.get("/api/parametres/agence")
    assert resp.status_code == 401


def test_get_agence_creates_default_if_missing(client, logged_in_employe):
    resp = client.get("/api/parametres/agence")
    assert resp.status_code == 200
    assert resp.json["nom"] == "Mon Agence de Location"


def test_update_agence_requires_admin(client, logged_in_employe):
    resp = client.put("/api/parametres/agence", json={"nom": "Ma Nouvelle Agence"})
    assert resp.status_code == 403


def test_update_agence_success(client, logged_in_admin):
    resp = client.put(
        "/api/parametres/agence",
        json={"nom": "Agence Atlas Car", "telephone": "0522000000", "adresse": "Casablanca"},
    )
    assert resp.status_code == 200
    assert resp.json["nom"] == "Agence Atlas Car"
    assert resp.json["telephone"] == "0522000000"

    resp = client.get("/api/parametres/agence")
    assert resp.json["nom"] == "Agence Atlas Car"


def test_update_agence_conditions_contrat(client, logged_in_admin):
    resp = client.put(
        "/api/parametres/agence",
        json={"nom": "Agence Atlas Car", "conditions_contrat": "1. Clause A\n2. Clause B"},
    )
    assert resp.status_code == 200
    assert resp.json["conditions_contrat"] == "1. Clause A\n2. Clause B"

    resp = client.get("/api/parametres/agence")
    assert resp.json["conditions_contrat"] == "1. Clause A\n2. Clause B"


def test_update_agence_empty_nom_rejected(client, logged_in_admin):
    resp = client.put("/api/parametres/agence", json={"nom": ""})
    assert resp.status_code == 400


def test_update_agence_partial_keeps_other_fields(client, logged_in_admin):
    client.put("/api/parametres/agence", json={"nom": "Agence Atlas Car", "telephone": "0522000000"})
    resp = client.put("/api/parametres/agence", json={"adresse": "Rabat"})
    assert resp.status_code == 200
    assert resp.json["nom"] == "Agence Atlas Car"
    assert resp.json["telephone"] == "0522000000"
    assert resp.json["adresse"] == "Rabat"


def test_upload_logo_requires_admin(client, logged_in_employe):
    resp = client.post(
        "/api/parametres/agence/logo",
        data={"fichier": (io.BytesIO(b"fake-png-bytes"), "logo.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 403


def test_upload_logo_success(client, logged_in_admin):
    resp = client.post(
        "/api/parametres/agence/logo",
        data={"fichier": (io.BytesIO(b"fake-png-bytes"), "logo.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.json["logo_url"].startswith("agence/logo/")
