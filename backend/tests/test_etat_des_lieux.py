import io
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
def reservation(client, logged_in_employe, db):
    c = Client(nom="Alami", prenom="Yassine", telephone="0600000000")
    v = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation="1-A-1",
        categorie="citadine",
        tarif_jour=Decimal("300.00"),
        statut=StatutVehicule.DISPONIBLE,
    )
    db.session.add_all([c, v])
    db.session.commit()
    resp = client.post(
        "/api/reservations",
        json={
            "client_id": c.id,
            "vehicule_id": v.id,
            "date_debut": "2026-08-10",
            "date_fin": "2026-08-15",
        },
    )
    assert resp.status_code == 201
    return resp.json


def test_liste_requires_login(client, reservation):
    client.post("/api/auth/logout")
    resp = client.get(f"/api/reservations/{reservation['id']}/etats-des-lieux")
    assert resp.status_code == 401


def test_upsert_creates_then_updates(client, reservation):
    rid = reservation["id"]
    resp = client.put(
        f"/api/reservations/{rid}/etats-des-lieux/depart",
        json={"kilometrage": 45120, "niveau_carburant": "plein", "degats": "RAS"},
    )
    assert resp.status_code == 200
    assert resp.json["type"] == "depart"
    assert resp.json["kilometrage"] == 45120
    assert resp.json["niveau_carburant"] == "plein"
    etat_id = resp.json["id"]

    resp = client.put(
        f"/api/reservations/{rid}/etats-des-lieux/depart",
        json={"kilometrage": 45200},
    )
    assert resp.status_code == 200
    assert resp.json["id"] == etat_id
    assert resp.json["kilometrage"] == 45200

    resp = client.get(f"/api/reservations/{rid}/etats-des-lieux")
    assert len(resp.json) == 1


def test_depart_and_retour_are_distinct(client, reservation):
    rid = reservation["id"]
    client.put(f"/api/reservations/{rid}/etats-des-lieux/depart", json={"kilometrage": 100})
    client.put(f"/api/reservations/{rid}/etats-des-lieux/retour", json={"kilometrage": 900})
    resp = client.get(f"/api/reservations/{rid}/etats-des-lieux")
    types = sorted(e["type"] for e in resp.json)
    assert types == ["depart", "retour"]


def test_upsert_unknown_type_rejected(client, reservation):
    resp = client.put(
        f"/api/reservations/{reservation['id']}/etats-des-lieux/milieu", json={}
    )
    assert resp.status_code == 400


def test_upsert_invalid_km_rejected(client, reservation):
    resp = client.put(
        f"/api/reservations/{reservation['id']}/etats-des-lieux/depart",
        json={"kilometrage": "beaucoup"},
    )
    assert resp.status_code == 400


def test_upsert_unknown_reservation_404(client, logged_in_employe):
    resp = client.put("/api/reservations/9999/etats-des-lieux/depart", json={})
    assert resp.status_code == 404


def _png_bytes():
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_photo_add_and_remove(client, reservation):
    rid = reservation["id"]
    etat = client.put(
        f"/api/reservations/{rid}/etats-des-lieux/depart", json={"kilometrage": 10}
    ).json
    resp = client.post(
        f"/api/etat-des-lieux/{etat['id']}/photo",
        data={"fichier": (io.BytesIO(_png_bytes()), "photo.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert len(resp.json["photos"]) == 1
    url = resp.json["photos"][0]

    resp = client.delete(f"/api/etat-des-lieux/{etat['id']}/photo", json={"url": url})
    assert resp.status_code == 200
    assert resp.json["photos"] == []


def test_pdf_endpoint(client, reservation):
    rid = reservation["id"]
    etat = client.put(
        f"/api/reservations/{rid}/etats-des-lieux/depart",
        json={"kilometrage": 45120, "niveau_carburant": "plein", "degats": "Rayure portière"},
    ).json
    resp = client.get(f"/api/etat-des-lieux/{etat['id']}/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_pdf_endpoint_arabic(client, reservation, db):
    from app.services.agence import get_or_create_agence

    agence = get_or_create_agence()
    agence.langue = "ar"
    db.session.commit()

    etat = client.put(
        f"/api/reservations/{reservation['id']}/etats-des-lieux/retour",
        json={"kilometrage": 45999, "niveau_carburant": "moitie"},
    ).json
    resp = client.get(f"/api/etat-des-lieux/{etat['id']}/pdf")
    assert resp.status_code == 200
    assert resp.data[:5] == b"%PDF-"
    assert len(resp.data) > 2000


def test_pdf_unknown_etat_404(client, logged_in_employe):
    resp = client.get("/api/etat-des-lieux/9999/pdf")
    assert resp.status_code == 404
