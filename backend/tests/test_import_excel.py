import io

import pytest
from openpyxl import Workbook

from app.models import Client, User, Vehicule
from app.models.enums import RoleUser


@pytest.fixture()
def logged_in_admin(client, db):
    admin = User(nom="Admin", email="admin@agence.local", role=RoleUser.ADMIN)
    admin.set_password("adminpass123")
    db.session.add(admin)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "admin@agence.local", "mot_de_passe": "adminpass123"})
    return admin


def _xlsx(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, quoi, data):
    return client.post(
        f"/api/import/{quoi}",
        data={"fichier": (io.BytesIO(data), "f.xlsx")},
        content_type="multipart/form-data",
    )


def test_import_vehicules_ok(client, logged_in_admin, db):
    data = _xlsx([
        ["Marque", "Modèle", "Immatriculation", "Catégorie", "Tarif/jour", "Carburant"],
        ["Dacia", "Logan", "1234-A-56", "Berline", "250", "diesel"],
        ["Renault", "Clio", "4590-B-12", "Citadine", "220,50", "essence"],
        ["Dacia", "Logan", "1234-A-56", "Berline", "999", ""],  # doublon -> ignoré
        ["Kia", "", "7788-C-1", "Citadine", "180", ""],  # modèle vide -> erreur
    ])
    resp = _upload(client, "vehicules", data)
    assert resp.status_code == 200
    j = resp.json
    assert j["cree"] == 2
    assert j["ignore"] == 1
    assert len(j["erreurs"]) == 1
    assert db.session.query(Vehicule).count() == 2


def test_import_vehicules_missing_column(client, logged_in_admin):
    data = _xlsx([["Marque", "Modèle"], ["Dacia", "Logan"]])
    resp = _upload(client, "vehicules", data)
    assert resp.status_code == 400
    assert "obligatoires" in resp.json["error"]


def test_import_clients_ok(client, logged_in_admin, db):
    data = _xlsx([
        ["Nom", "Prénom", "Téléphone", "Email", "CIN"],
        ["Bennani", "Yassine", "0661000000", "y@example.ma", "BE123"],
        ["Alaoui", "Sara", "0662000000", "", ""],
    ])
    resp = _upload(client, "clients", data)
    assert resp.status_code == 200
    assert resp.json["cree"] == 2
    assert db.session.query(Client).count() == 2


def test_import_requires_admin(client, db):
    emp = User(nom="E", email="e@a.local", role=RoleUser.EMPLOYE)
    emp.set_password("employe123")
    db.session.add(emp)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "e@a.local", "mot_de_passe": "employe123"})
    resp = _upload(client, "vehicules", _xlsx([["Marque"]]))
    assert resp.status_code == 403


def test_import_rejects_non_xlsx(client, logged_in_admin):
    resp = client.post(
        "/api/import/vehicules",
        data={"fichier": (io.BytesIO(b"not excel"), "f.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_modele_download(client, logged_in_admin):
    resp = client.get("/api/import/modele/vehicules")
    assert resp.status_code == 200
    assert "spreadsheet" in resp.mimetype
