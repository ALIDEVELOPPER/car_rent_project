import pytest

from app.models import User
from app.models.enums import RoleUser
from app.utils.decorators import role_required


@pytest.fixture()
def admin_user(db):
    user = User(nom="Admin", email="admin@agence.local", role=RoleUser.ADMIN)
    user.set_password("adminpass123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def employe_user(db):
    user = User(nom="Employe", email="employe@agence.local", role=RoleUser.EMPLOYE)
    user.set_password("employepass123")
    db.session.add(user)
    db.session.commit()
    return user


def test_login_success(client, admin_user):
    resp = client.post(
        "/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"}
    )
    assert resp.status_code == 200
    assert resp.json["email"] == "admin@agence.local"
    assert resp.json["role"] == "admin"


def test_login_wrong_password(client, admin_user):
    resp = client.post(
        "/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "wrong"}
    )
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post(
        "/api/auth/login", json={"email": "nobody@agence.local", "mot_de_passe": "whatever"}
    )
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"email": "admin@agence.local"})
    assert resp.status_code == 400


def test_login_inactive_user_rejected(client, db):
    user = User(nom="Inactif", email="inactif@agence.local", role=RoleUser.EMPLOYE, actif=False)
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()

    resp = client.post(
        "/api/auth/login", json={"email": "inactif@agence.local", "mot_de_passe": "secret123"}
    )
    assert resp.status_code == 401


def test_me_requires_login(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_after_login(client, admin_user):
    client.post(
        "/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"}
    )
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json["email"] == "admin@agence.local"


def test_logout_clears_session(client, admin_user):
    client.post(
        "/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"}
    )
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_role_required_blocks_wrong_role(app, employe_user):
    @app.route("/api/_test/admin-only")
    @role_required(RoleUser.ADMIN)
    def admin_only():
        return "ok"

    with app.test_client() as c:
        c.post(
            "/api/auth/login",
            json={"email": "employe@agence.local", "mot_de_passe": "employepass123"},
        )
        resp = c.get("/api/_test/admin-only")
        assert resp.status_code == 403


def test_role_required_allows_correct_role(app, admin_user):
    @app.route("/api/_test/admin-only-2")
    @role_required(RoleUser.ADMIN)
    def admin_only_2():
        return "ok"

    with app.test_client() as c:
        c.post(
            "/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"}
        )
        resp = c.get("/api/_test/admin-only-2")
        assert resp.status_code == 200
