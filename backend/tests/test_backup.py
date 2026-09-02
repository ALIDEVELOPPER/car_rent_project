import io

import pytest

from app.models import User, Vehicule
from app.models.enums import RoleUser
from app.services.backup import RestaurationError, creer_sauvegarde, restaurer_sauvegarde


@pytest.fixture()
def logged_in_admin(client, db):
    admin = User(nom="Admin", email="admin@agence.local", role=RoleUser.ADMIN)
    admin.set_password("adminpass123")
    db.session.add(admin)
    db.session.add(Vehicule(marque="Dacia", modele="Logan", immatriculation="1-A-1",
                            categorie="berline", tarif_jour=250))
    db.session.commit()
    client.post("/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"})
    return admin


def test_sauvegarde_endpoint_returns_zip(client, logged_in_admin):
    resp = client.post("/api/sauvegarde", json={})
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    assert resp.data[:2] == b"PK"


def test_sauvegarde_requires_admin(client, db):
    emp = User(nom="E", email="e@a.local", role=RoleUser.EMPLOYE)
    emp.set_password("employe123")
    db.session.add(emp)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "e@a.local", "mot_de_passe": "employe123"})
    assert client.post("/api/sauvegarde", json={}).status_code == 403


def test_sauvegarde_chiffree_puis_restauration(app, client, logged_in_admin, tmp_path, monkeypatch):
    from app.services import backup as backup_mod

    fake_db = tmp_path / "app.db"
    fake_db.write_bytes(b"SQLite format 3\x00 fake content")
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "vehicules").mkdir()
    (uploads / "vehicules" / "photo.jpg").write_bytes(b"jpegdata")
    monkeypatch.setattr(backup_mod, "_db_path", lambda: fake_db)
    monkeypatch.setattr(backup_mod, "_uploads_path", lambda: uploads)
    monkeypatch.setattr(backup_mod, "get_app_data_dir", lambda: tmp_path)

    with app.app_context():
        contenu, nom = creer_sauvegarde(password="secret123")
    assert nom.endswith(".zip")

    with app.app_context():
        with pytest.raises(RestaurationError):
            restaurer_sauvegarde(contenu, password="mauvais")

    with app.app_context():
        res = restaurer_sauvegarde(contenu, password="secret123")
    assert res["restart_required"] is True
    assert (tmp_path / "app.db.incoming").exists()


def test_restauration_rejette_fichier_invalide(client, logged_in_admin):
    resp = client.post(
        "/api/sauvegarde/restauration",
        data={"fichier": (io.BytesIO(b"pas un zip"), "x.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
