from datetime import date
from decimal import Decimal

import pytest

from app.models import Client, Reservation, User, Vehicule
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


def test_list_utilisateurs_requires_admin(client, logged_in_employe):
    resp = client.get("/api/parametres/utilisateurs")
    assert resp.status_code == 403


def test_list_utilisateurs_success(client, logged_in_admin):
    resp = client.get("/api/parametres/utilisateurs")
    assert resp.status_code == 200
    assert any(u["email"] == "admin@agence.local" for u in resp.json)
    assert "mot_de_passe_hash" not in resp.json[0]


def test_create_utilisateur_missing_fields(client, logged_in_admin):
    resp = client.post("/api/parametres/utilisateurs", json={"nom": "Sara"})
    assert resp.status_code == 400


def test_create_utilisateur_invalid_role(client, logged_in_admin):
    resp = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123", "role": "super_admin"},
    )
    assert resp.status_code == 400


def test_create_utilisateur_success_defaults_to_employe(client, logged_in_admin):
    resp = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    )
    assert resp.status_code == 201
    assert resp.json["role"] == "employe"
    assert resp.json["actif"] is True


def test_create_utilisateur_duplicate_email_conflict(client, logged_in_admin):
    client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    )
    resp = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara Bis", "email": "sara@agence.local", "mot_de_passe": "secret456"},
    )
    assert resp.status_code == 409


def test_get_unknown_utilisateur_returns_404(client, logged_in_admin):
    resp = client.get("/api/parametres/utilisateurs/9999")
    assert resp.status_code == 404


def test_update_utilisateur_password_reset_allows_new_login(client, logged_in_admin):
    created = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    ).json

    resp = client.put(
        f"/api/parametres/utilisateurs/{created['id']}", json={"mot_de_passe": "nouveaumdp456"}
    )
    assert resp.status_code == 200

    login_resp = client.post(
        "/api/auth/login", json={"email": "sara@agence.local", "mot_de_passe": "nouveaumdp456"}
    )
    assert login_resp.status_code == 200


def test_update_utilisateur_empty_nom_rejected(client, logged_in_admin):
    created = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    ).json

    resp = client.put(f"/api/parametres/utilisateurs/{created['id']}", json={"nom": ""})
    assert resp.status_code == 400


def test_demote_last_admin_blocked(client, logged_in_admin):
    resp = client.put(
        f"/api/parametres/utilisateurs/{logged_in_admin.id}", json={"role": "employe"}
    )
    assert resp.status_code == 409


def test_demote_admin_allowed_when_another_admin_active(client, logged_in_admin, db):
    other_admin = User(nom="Autre Admin", email="autre-admin@agence.local", role=RoleUser.ADMIN)
    other_admin.set_password("secret123")
    db.session.add(other_admin)
    db.session.commit()

    resp = client.put(
        f"/api/parametres/utilisateurs/{other_admin.id}", json={"role": "employe"}
    )
    assert resp.status_code == 200
    assert resp.json["role"] == "employe"


def test_toggle_actif_requires_field(client, logged_in_admin):
    created = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    ).json

    resp = client.patch(f"/api/parametres/utilisateurs/{created['id']}/actif", json={})
    assert resp.status_code == 400


def test_deactivate_utilisateur_success(client, logged_in_admin):
    created = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    ).json

    resp = client.patch(f"/api/parametres/utilisateurs/{created['id']}/actif", json={"actif": False})
    assert resp.status_code == 200
    assert resp.json["actif"] is False


def test_deactivate_last_admin_blocked(client, logged_in_admin):
    resp = client.patch(
        f"/api/parametres/utilisateurs/{logged_in_admin.id}/actif", json={"actif": False}
    )
    assert resp.status_code == 409


def test_delete_self_blocked(client, logged_in_admin):
    resp = client.delete(f"/api/parametres/utilisateurs/{logged_in_admin.id}")
    assert resp.status_code == 400


def test_delete_utilisateur_success(client, logged_in_admin):
    created = client.post(
        "/api/parametres/utilisateurs",
        json={"nom": "Sara", "email": "sara@agence.local", "mot_de_passe": "secret123"},
    ).json

    resp = client.delete(f"/api/parametres/utilisateurs/{created['id']}")
    assert resp.status_code == 204

    resp = client.get(f"/api/parametres/utilisateurs/{created['id']}")
    assert resp.status_code == 404


def test_delete_utilisateur_blocked_when_referenced_by_reservation(client, logged_in_admin, db):
    other_user = User(nom="Ancien Employe", email="ancien@agence.local", role=RoleUser.EMPLOYE)
    other_user.set_password("secret123")
    db.session.add(other_user)
    db.session.commit()

    client_obj = Client(nom="Alami", prenom="Yassine", telephone="0600000000")
    vehicule = Vehicule(
        marque="Renault",
        modele="Clio",
        immatriculation="1-A-1",
        categorie="citadine",
        tarif_jour=Decimal("300"),
    )
    db.session.add_all([client_obj, vehicule])
    db.session.commit()

    reservation = Reservation(
        client_id=client_obj.id,
        vehicule_id=vehicule.id,
        created_by=other_user.id,
        date_debut=date(2026, 8, 10),
        date_fin=date(2026, 8, 15),
        prix_jour_applique=vehicule.tarif_jour,
        montant_total=vehicule.tarif_jour * 5,
    )
    db.session.add(reservation)
    db.session.commit()

    resp = client.delete(f"/api/parametres/utilisateurs/{other_user.id}")
    assert resp.status_code == 409
