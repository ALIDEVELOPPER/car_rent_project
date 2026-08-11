from app.models import User
from app.models.enums import RoleUser


def test_status_true_when_no_users(client):
    resp = client.get("/api/setup/status")
    assert resp.status_code == 200
    assert resp.json["needs_setup"] is True


def test_status_false_when_users_exist(client, db):
    user = User(nom="Admin", email="admin@agence.local", role=RoleUser.ADMIN)
    user.set_password("adminpass123")
    db.session.add(user)
    db.session.commit()

    resp = client.get("/api/setup/status")
    assert resp.status_code == 200
    assert resp.json["needs_setup"] is False


def test_create_first_admin_success(client):
    resp = client.post(
        "/api/setup/admin",
        json={"nom": "Admin", "email": "admin@agence.local", "mot_de_passe": "adminpass123"},
    )
    assert resp.status_code == 201
    assert resp.json["email"] == "admin@agence.local"

    login_resp = client.post(
        "/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json["role"] == "admin"


def test_create_first_admin_missing_fields(client):
    resp = client.post("/api/setup/admin", json={"nom": "Admin"})
    assert resp.status_code == 400


def test_create_first_admin_weak_password(client):
    resp = client.post(
        "/api/setup/admin",
        json={"nom": "Admin", "email": "admin@agence.local", "mot_de_passe": "short"},
    )
    assert resp.status_code == 400


def test_create_first_admin_blocked_once_user_exists(client, db):
    user = User(nom="Existant", email="existant@agence.local", role=RoleUser.EMPLOYE)
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    resp = client.post(
        "/api/setup/admin",
        json={"nom": "Admin", "email": "admin@agence.local", "mot_de_passe": "adminpass123"},
    )
    assert resp.status_code == 409
