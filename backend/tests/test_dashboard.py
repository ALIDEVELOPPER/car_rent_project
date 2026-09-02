import pytest

from app.models import User
from app.models.enums import RoleUser


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


def test_kpis_requires_login(client):
    resp = client.get("/api/dashboard/kpis")
    assert resp.status_code == 401


def test_dashboard_operationnel_requires_login(client):
    assert client.get("/api/dashboard").status_code == 401


def test_dashboard_operationnel_shape_empty(client, logged_in_employe):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json
    assert set(data.keys()) == {"date", "agenda", "impayes", "revenus", "flotte", "prochains_jours"}
    assert set(data["agenda"].keys()) == {"departs", "retours", "retards"}
    assert data["agenda"] == {"departs": [], "retours": [], "retards": []}
    assert data["impayes"]["nombre"] == 0
    assert data["impayes"]["total"] in ("0", "0.00")
    assert data["revenus"]["variation_pct"] is None
    assert len(data["prochains_jours"]) == 7
    assert data["flotte"]["total"] == 0


def test_dashboard_operationnel_with_data(client, logged_in_employe, db):
    from datetime import date, timedelta
    from decimal import Decimal

    from app.models import Client, Reservation, Vehicule
    from app.models.enums import StatutReservation, StatutVehicule

    today = date.today()
    c = Client(nom="Test", prenom="Client", telephone="0600000000")
    v1 = Vehicule(marque="Dacia", modele="Logan", immatriculation="1-A-1", categorie="berline",
                  tarif_jour=Decimal("200"), statut=StatutVehicule.LOUE)
    v2 = Vehicule(marque="Kia", modele="Picanto", immatriculation="2-B-2", categorie="citadine",
                  tarif_jour=Decimal("180"), statut=StatutVehicule.DISPONIBLE)
    db.session.add_all([c, v1, v2])
    db.session.flush()
    # retard : en cours, fin passée
    db.session.add(Reservation(client_id=c.id, vehicule_id=v1.id, date_debut=today - timedelta(days=5),
                               date_fin=today - timedelta(days=2), statut=StatutReservation.EN_COURS,
                               prix_jour_applique=Decimal("200"), montant_total=Decimal("600")))
    # départ du jour
    db.session.add(Reservation(client_id=c.id, vehicule_id=v2.id, date_debut=today,
                               date_fin=today + timedelta(days=3), statut=StatutReservation.CONFIRMEE,
                               prix_jour_applique=Decimal("180"), montant_total=Decimal("540")))
    db.session.commit()

    data = client.get("/api/dashboard").json
    assert len(data["agenda"]["retards"]) == 1
    assert data["agenda"]["retards"][0]["retard_jours"] == 2
    assert len(data["agenda"]["departs"]) == 1
    assert data["flotte"]["loue"] == 1
    assert data["flotte"]["disponible"] == 1
    assert data["prochains_jours"][0]["reservations"] == [] or isinstance(data["prochains_jours"][0]["reservations"], list)


def test_kpis_shape(client, logged_in_employe):
    resp = client.get("/api/dashboard/kpis")
    assert resp.status_code == 200
    assert set(resp.json.keys()) == {
        "taux_occupation",
        "revenus_du_mois",
        "vehicules_disponibles",
        "reservations_en_cours",
    }


def test_revenus_par_mois_default_12_months(client, logged_in_employe):
    resp = client.get("/api/dashboard/revenus-par-mois")
    assert resp.status_code == 200
    assert len(resp.json) == 12


def test_revenus_par_mois_custom_range_clamped(client, logged_in_employe):
    resp = client.get("/api/dashboard/revenus-par-mois?mois=100")
    assert resp.status_code == 200
    assert len(resp.json) == 36


def test_top_vehicules_empty_fleet(client, logged_in_employe):
    resp = client.get("/api/dashboard/top-vehicules")
    assert resp.status_code == 200
    assert resp.json == []


def test_top_vehicules_reflects_reservations(client, logged_in_employe):
    client_resp = client.post(
        "/api/clients", json={"nom": "Alami", "prenom": "Yassine", "telephone": "0600000000"}
    )
    vehicule_resp = client.post(
        "/api/vehicules",
        json={
            "marque": "Renault",
            "modele": "Clio",
            "immatriculation": "1-A-1",
            "categorie": "citadine",
            "tarif_jour": "300",
        },
    )

    client.post(
        "/api/reservations",
        json={
            "client_id": client_resp.json["id"],
            "vehicule_id": vehicule_resp.json["id"],
            "date_debut": "2026-08-10",
            "date_fin": "2026-08-15",
        },
    )

    resp = client.get("/api/dashboard/top-vehicules")
    assert resp.status_code == 200
    assert resp.json[0]["vehicule_id"] == vehicule_resp.json["id"]
    assert resp.json[0]["nombre_reservations"] == 1
