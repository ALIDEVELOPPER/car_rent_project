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


def _create_client(client, **overrides):
    payload = {"nom": "Alami", "prenom": "Yassine", "telephone": "0600000000"}
    payload.update(overrides)
    resp = client.post("/api/clients", json=payload)
    assert resp.status_code == 201
    return resp.json


def test_create_client_requires_login(client):
    resp = client.post(
        "/api/clients", json={"nom": "Alami", "prenom": "Yassine", "telephone": "0600000000"}
    )
    assert resp.status_code == 401


def test_create_client_missing_fields(client, logged_in_employe):
    resp = client.post("/api/clients", json={"nom": "Alami"})
    assert resp.status_code == 400


def test_create_and_get_client(client, logged_in_employe):
    created = _create_client(client)

    resp = client.get(f"/api/clients/{created['id']}")
    assert resp.status_code == 200
    assert resp.json["nom"] == "Alami"
    assert resp.json["reservations"] == []


def test_get_unknown_client_returns_404(client, logged_in_employe):
    resp = client.get("/api/clients/9999")
    assert resp.status_code == 404


def test_list_clients_search(client, logged_in_employe):
    _create_client(client, nom="Alami", prenom="Yassine", telephone="0600000001")
    _create_client(client, nom="Bennani", prenom="Sara", telephone="0600000002")

    resp = client.get("/api/clients?q=alami")
    assert resp.status_code == 200
    assert len(resp.json) == 1
    assert resp.json[0]["nom"] == "Alami"


def test_update_client(client, logged_in_employe):
    created = _create_client(client)

    resp = client.put(f"/api/clients/{created['id']}", json={"email": "yassine@example.com"})
    assert resp.status_code == 200
    assert resp.json["email"] == "yassine@example.com"


def test_update_client_invalid_date(client, logged_in_employe):
    created = _create_client(client)

    resp = client.put(f"/api/clients/{created['id']}", json={"date_naissance": "not-a-date"})
    assert resp.status_code == 400


def test_update_client_invalid_type_piece(client, logged_in_employe):
    created = _create_client(client)

    resp = client.put(f"/api/clients/{created['id']}", json={"type_piece_identite": "carte_vitale"})
    assert resp.status_code == 400


def test_delete_client_requires_admin(client, logged_in_employe):
    created = _create_client(client)

    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 403


def test_delete_client_success(client, logged_in_admin):
    created = _create_client(client)

    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/api/clients/{created['id']}")
    assert resp.status_code == 404


def test_delete_client_blocked_by_reservations(client, logged_in_admin, db):
    created = _create_client(client)
    client_obj = db.session.get(Client, created["id"])

    vehicule = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation="12345-A-6",
        categorie="citadine",
        tarif_jour=350,
        statut=StatutVehicule.DISPONIBLE,
    )
    db.session.add(vehicule)
    db.session.commit()

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

    resp = client.delete(f"/api/clients/{client_obj.id}")
    assert resp.status_code == 409

    resp = client.get(f"/api/clients/{client_obj.id}")
    assert resp.status_code == 200


def test_upload_document_identite_success(client, logged_in_employe):
    created = _create_client(client)

    resp = client.post(
        f"/api/clients/{created['id']}/document-identite",
        data={"fichier": (io.BytesIO(b"%PDF-1.4 fake content"), "cni.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    url = resp.json["document_identite_url"]
    assert url.startswith(f"clients/{created['id']}/identite/")

    download = client.get(f"/api/uploads/{url}")
    assert download.status_code == 200
    assert download.data == b"%PDF-1.4 fake content"


def test_upload_rejects_bad_extension(client, logged_in_employe):
    created = _create_client(client)

    resp = client.post(
        f"/api/clients/{created['id']}/permis",
        data={"fichier": (io.BytesIO(b"MZ..."), "malware.exe")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_upload_missing_file(client, logged_in_employe):
    created = _create_client(client)

    resp = client.post(
        f"/api/clients/{created['id']}/permis",
        data={},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_uploads_path_traversal_blocked(client, logged_in_employe):
    resp = client.get("/api/uploads/../../../../etc/passwd")
    assert resp.status_code == 404
