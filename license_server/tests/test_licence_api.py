from app.extensions import db
from app.models import Licence, StatutLicence


def test_create_licence_requires_admin_token(client):
    res = client.post("/admin/licences", json={"nom_client": "Agence Test"})
    assert res.status_code == 401


def test_create_licence(client, admin_headers):
    res = client.post("/admin/licences", json={"nom_client": "Agence Test"}, headers=admin_headers)
    assert res.status_code == 201
    data = res.get_json()
    assert data["nom_client"] == "Agence Test"
    assert data["statut"] == "essai"
    assert data["code"]


def test_create_licence_with_explicit_code_rejects_duplicate(client, admin_headers):
    client.post("/admin/licences", json={"nom_client": "A", "code": "ABC123"}, headers=admin_headers)
    res = client.post("/admin/licences", json={"nom_client": "B", "code": "ABC123"}, headers=admin_headers)
    assert res.status_code == 409


def test_activate_unknown_code(client):
    res = client.post("/activate", json={"code": "INCONNU"})
    assert res.status_code == 404


def test_activate_starts_trial(client, admin_headers):
    created = client.post(
        "/admin/licences", json={"nom_client": "Agence Test", "code": "TRIAL1"}, headers=admin_headers
    ).get_json()
    assert created["activated_at"] is None
    assert created["essai_expire_le"] is None

    res = client.post("/activate", json={"code": "TRIAL1"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["statut"] == "essai"
    assert data["activated_at"] is not None
    assert data["essai_expire_le"] is not None
    assert data["valide"] is True


def test_activate_is_idempotent(client, admin_headers):
    client.post("/admin/licences", json={"nom_client": "Agence Test", "code": "TRIAL2"}, headers=admin_headers)

    first = client.post("/activate", json={"code": "TRIAL2"}).get_json()
    second = client.post("/activate", json={"code": "TRIAL2"}).get_json()

    assert first["activated_at"] == second["activated_at"]
    assert first["essai_expire_le"] == second["essai_expire_le"]


def test_status_reflects_current_state(client, admin_headers):
    client.post("/admin/licences", json={"nom_client": "Agence Test", "code": "STATUS1"}, headers=admin_headers)
    client.post("/activate", json={"code": "STATUS1"})

    res = client.get("/status", query_string={"code": "STATUS1"})
    assert res.status_code == 200
    assert res.get_json()["statut"] == "essai"


def test_admin_can_suspend_and_reactivate(client, admin_headers, app):
    created = client.post(
        "/admin/licences", json={"nom_client": "Agence Test", "code": "SUSP1"}, headers=admin_headers
    ).get_json()
    licence_id = created["id"]

    res = client.patch(f"/admin/licences/{licence_id}", json={"statut": "suspendu"}, headers=admin_headers)
    assert res.get_json()["statut"] == "suspendu"

    with app.app_context():
        licence = db.session.get(Licence, licence_id)
        assert licence.statut == StatutLicence.SUSPENDU
        assert licence.est_valide is False

    res = client.patch(f"/admin/licences/{licence_id}", json={"statut": "actif"}, headers=admin_headers)
    assert res.get_json()["statut"] == "actif"
    assert res.get_json()["valide"] is True


def test_admin_can_delete_licence(client, admin_headers):
    created = client.post(
        "/admin/licences", json={"nom_client": "Agence Test", "code": "DEL1"}, headers=admin_headers
    ).get_json()

    res = client.delete(f"/admin/licences/{created['id']}", headers=admin_headers)
    assert res.status_code == 204

    res = client.get("/status", query_string={"code": "DEL1"})
    assert res.status_code == 404
