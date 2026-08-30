from datetime import timedelta

from app.extensions import db
from app.models import Installation, StatutInstallation, utcnow


def _register(client, installation_id="inst-1", fingerprint="fp-1", **extra):
    payload = {"installation_id": installation_id, "machine_fingerprint": fingerprint, **extra}
    return client.post("/register", json=payload)


# --- /register -------------------------------------------------------------


def test_register_requires_fields(client):
    assert client.post("/register", json={"installation_id": "x"}).status_code == 400
    assert client.post("/register", json={"machine_fingerprint": "x"}).status_code == 400


def test_register_creates_trial(client):
    res = _register(client, nom_agence="Agence Test", hostname="PC-01", os_info="Windows 11")
    assert res.status_code == 200
    data = res.get_json()
    assert data["statut"] == "essai"
    assert data["secret"]
    assert data["jours_essai_restants"] == 7
    assert data["essai_expire_le"] < data["bloque_le"]


def test_register_idempotent_by_installation_id(client):
    first = _register(client).get_json()
    second = _register(client).get_json()
    assert first["secret"] == second["secret"]
    assert first["essai_expire_le"] == second["essai_expire_le"]
    assert db.session.query(Installation).count() == 1


def test_register_dedup_by_fingerprint_no_new_trial(client, app):
    first = _register(client, installation_id="inst-A", fingerprint="same-fp").get_json()

    with app.app_context():
        inst = db.session.execute(
            db.select(Installation).filter_by(installation_id="inst-A")
        ).scalar_one()
        inst.essai_expire_le = utcnow() - timedelta(days=3)
        db.session.commit()

    # Nouveau installation_id (cache supprimé) mais même machine -> même installation, essai déjà expiré.
    second = _register(client, installation_id="inst-B", fingerprint="same-fp").get_json()
    assert second["installation_id"] == "inst-A"
    assert second["secret"] == first["secret"]
    assert second["jours_essai_restants"] == 0
    assert db.session.query(Installation).count() == 1


# --- /heartbeat -----------------------------------------------------------


def test_heartbeat_requires_valid_secret(client):
    _register(client).get_json()
    assert client.post("/heartbeat", json={"installation_id": "inst-1", "secret": "nope"}).status_code == 401
    assert client.post("/heartbeat", json={"installation_id": "inconnu", "secret": "x"}).status_code == 401


def test_heartbeat_returns_status_and_updates_last_seen(client, app):
    secret = _register(client).get_json()["secret"]

    with app.app_context():
        inst = db.session.execute(db.select(Installation)).scalar_one()
        inst.last_seen_at = utcnow() - timedelta(days=2)
        db.session.commit()

    res = client.post("/heartbeat", json={"installation_id": "inst-1", "secret": secret})
    assert res.status_code == 200
    assert res.get_json()["statut"] == "essai"
    assert "secret" not in res.get_json()

    with app.app_context():
        inst = db.session.execute(db.select(Installation)).scalar_one()
        assert (utcnow() - inst.last_seen_at) < timedelta(minutes=1)


def test_heartbeat_reflects_suspension(client, app, admin_headers):
    secret = _register(client).get_json()["secret"]
    inst_id = client.get("/admin/installations", headers=admin_headers).get_json()[0]["id"]
    client.post(f"/admin/installations/{inst_id}/block", headers=admin_headers)

    res = client.post("/heartbeat", json={"installation_id": "inst-1", "secret": secret})
    assert res.get_json()["statut"] == "suspendu"


# --- admin --------------------------------------------------------------


def test_admin_requires_token(client):
    assert client.get("/admin/installations").status_code == 401


def test_admin_list_and_filter(client, admin_headers):
    _register(client, installation_id="i1", fingerprint="f1", nom_agence="Alpha")
    _register(client, installation_id="i2", fingerprint="f2", nom_agence="Beta")

    all_rows = client.get("/admin/installations", headers=admin_headers).get_json()
    assert len(all_rows) == 2

    filtered = client.get("/admin/installations?q=alph", headers=admin_headers).get_json()
    assert [r["nom_agence"] for r in filtered] == ["Alpha"]

    essai_only = client.get("/admin/installations?statut=essai", headers=admin_headers).get_json()
    assert len(essai_only) == 2
    assert client.get("/admin/installations?statut=actif", headers=admin_headers).get_json() == []


def test_admin_approve_then_block_then_reactivate(client, admin_headers):
    _register(client)
    inst_id = client.get("/admin/installations", headers=admin_headers).get_json()[0]["id"]

    approved = client.post(f"/admin/installations/{inst_id}/approve", headers=admin_headers).get_json()
    assert approved["statut"] == "actif"
    assert approved["valide"] is True
    assert approved["activated_at"] is not None

    blocked = client.post(f"/admin/installations/{inst_id}/block", headers=admin_headers).get_json()
    assert blocked["statut"] == "suspendu"
    assert blocked["valide"] is False
    assert blocked["suspended_at"] is not None

    reactivated = client.patch(
        f"/admin/installations/{inst_id}", json={"statut": "actif"}, headers=admin_headers
    ).get_json()
    assert reactivated["statut"] == "actif"
    assert reactivated["valide"] is True


def test_admin_extend_trial(client, admin_headers, app):
    _register(client)
    inst_id = client.get("/admin/installations", headers=admin_headers).get_json()[0]["id"]

    with app.app_context():
        inst = db.session.execute(db.select(Installation)).scalar_one()
        inst.essai_expire_le = utcnow() - timedelta(days=1)
        db.session.commit()

    extended = client.post(
        f"/admin/installations/{inst_id}/extend", json={"days": 10}, headers=admin_headers
    ).get_json()
    assert extended["statut"] == "essai"
    assert extended["jours_essai_restants"] == 10


def test_admin_edit_metadata(client, admin_headers):
    _register(client)
    inst_id = client.get("/admin/installations", headers=admin_headers).get_json()[0]["id"]
    res = client.patch(
        f"/admin/installations/{inst_id}",
        json={"email_contact": "a@b.com", "plan": "annuel", "note": "payé le 30/08"},
        headers=admin_headers,
    ).get_json()
    assert res["email_contact"] == "a@b.com"
    assert res["plan"] == "annuel"
    assert res["note"] == "payé le 30/08"


def test_admin_delete(client, admin_headers):
    _register(client)
    inst_id = client.get("/admin/installations", headers=admin_headers).get_json()[0]["id"]
    assert client.delete(f"/admin/installations/{inst_id}", headers=admin_headers).status_code == 204
    assert client.get("/admin/installations", headers=admin_headers).get_json() == []


# --- modèle -------------------------------------------------------------


def test_installation_validity_transitions(app):
    with app.app_context():
        inst = Installation(installation_id="m1", machine_fingerprint="mf1")
        inst.start_trial()
        db.session.add(inst)
        db.session.commit()

        assert inst.est_valide is True

        inst.essai_expire_le = utcnow() - timedelta(hours=1)  # dans la grâce (1j)
        assert inst.est_valide is True

        inst.essai_expire_le = utcnow() - timedelta(days=2)   # grâce dépassée
        assert inst.est_valide is False

        inst.approve()
        assert inst.est_valide is True

        inst.block()
        assert inst.est_valide is False
