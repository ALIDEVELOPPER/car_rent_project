from datetime import timedelta

import pytest
import requests

from app.services import licence as licence_service


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Empêche les tests d'écrire licence.json dans backend/instance/ (dossier réel)."""
    monkeypatch.setattr(licence_service, "get_app_data_dir", lambda: tmp_path)
    return tmp_path


def _iso(dt):
    return dt.isoformat()


def _write_cache(monkeypatch, **overrides):
    now = licence_service._now()
    data = {
        "code": "ABC123",
        "statut": "essai",
        "essai_expire_le": _iso(now + timedelta(days=3)),
        "activated_at": _iso(now - timedelta(days=4)),
        "last_checked_at": _iso(now),
    }
    data.update(overrides)
    licence_service._save_cache(data)
    return data


# --- get_state --------------------------------------------------------------


def test_get_state_no_cache_requires_activation():
    state = licence_service.get_state("http://fake")
    assert state == {"activated": False, "blocked": True, "reason": "activation_requise", "cache": None}


def test_get_state_actif_not_blocked(monkeypatch):
    _write_cache(monkeypatch, statut="actif", essai_expire_le=None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False
    assert state["activated"] is True


def test_get_state_suspendu_blocked(monkeypatch):
    _write_cache(monkeypatch, statut="suspendu")
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "suspendu"


def test_get_state_essai_en_cours_not_blocked(monkeypatch):
    _write_cache(monkeypatch, statut="essai", essai_expire_le=_iso(licence_service._now() + timedelta(days=2)))
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False


def test_get_state_essai_expire_refresh_confirms_actif(monkeypatch):
    _write_cache(
        monkeypatch,
        statut="essai",
        essai_expire_le=_iso(licence_service._now() - timedelta(days=1)),
        last_checked_at=_iso(licence_service._now() - timedelta(days=2)),
    )

    def fake_refresh(code, url):
        return {"code": code, "statut": "actif", "essai_expire_le": None, "last_checked_at": _iso(licence_service._now())}

    monkeypatch.setattr(licence_service, "_refresh", fake_refresh)

    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False
    assert state["cache"]["statut"] == "actif"


def test_get_state_essai_expire_refresh_confirms_not_paid_blocks(monkeypatch):
    expired = licence_service._now() - timedelta(days=1)
    _write_cache(
        monkeypatch,
        statut="essai",
        essai_expire_le=_iso(expired),
        last_checked_at=_iso(expired - timedelta(days=1)),
    )

    def fake_refresh(code, url):
        return {
            "code": code,
            "statut": "essai",
            "essai_expire_le": _iso(expired),
            "last_checked_at": _iso(licence_service._now()),
        }

    monkeypatch.setattr(licence_service, "_refresh", fake_refresh)

    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "essai_expire"


def test_get_state_essai_expire_offline_within_grace_not_blocked(monkeypatch):
    expired = licence_service._now() - timedelta(days=1)
    _write_cache(monkeypatch, statut="essai", essai_expire_le=_iso(expired), last_checked_at=_iso(expired - timedelta(hours=1)))

    monkeypatch.setattr(licence_service, "_refresh", lambda code, url: None)

    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False


def test_get_state_essai_expire_offline_past_grace_blocked(monkeypatch):
    expired = licence_service._now() - timedelta(days=licence_service.GRACE_DAYS + 1)
    _write_cache(monkeypatch, statut="essai", essai_expire_le=_iso(expired), last_checked_at=_iso(expired - timedelta(hours=1)))

    monkeypatch.setattr(licence_service, "_refresh", lambda code, url: None)

    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "verification_impossible"


def test_get_state_periodic_recheck_detects_suspension(monkeypatch):
    # Statut en cache "actif", mais plus de 24h depuis la dernière vérification :
    # une nouvelle suspension côté serveur doit être détectée.
    _write_cache(
        monkeypatch,
        statut="actif",
        essai_expire_le=None,
        last_checked_at=_iso(licence_service._now() - timedelta(hours=25)),
    )

    def fake_refresh(code, url):
        return {"code": code, "statut": "suspendu", "essai_expire_le": None, "last_checked_at": _iso(licence_service._now())}

    monkeypatch.setattr(licence_service, "_refresh", fake_refresh)

    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "suspendu"


def test_get_state_recent_check_skips_network(monkeypatch):
    _write_cache(monkeypatch, statut="actif", essai_expire_le=None, last_checked_at=_iso(licence_service._now()))

    def fail_refresh(code, url):
        raise AssertionError("ne devrait pas être appelé")

    monkeypatch.setattr(licence_service, "_refresh", fail_refresh)

    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False


def test_get_state_force_always_refreshes(monkeypatch):
    _write_cache(monkeypatch, statut="actif", essai_expire_le=None, last_checked_at=_iso(licence_service._now()))

    calls = []

    def fake_refresh(code, url):
        calls.append(code)
        return {"code": code, "statut": "suspendu", "essai_expire_le": None, "last_checked_at": _iso(licence_service._now())}

    monkeypatch.setattr(licence_service, "_refresh", fake_refresh)

    state = licence_service.get_state("http://fake", force=True)
    assert calls == ["ABC123"]
    assert state["blocked"] is True


# --- activate ----------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


def test_activate_success_writes_cache(monkeypatch):
    def fake_post(url, json, timeout):
        return _FakeResponse(200, {"statut": "essai", "essai_expire_le": _iso(licence_service._now() + timedelta(days=7))})

    monkeypatch.setattr(licence_service.requests, "post", fake_post)

    result = licence_service.activate("ABC123", "http://fake")
    assert result["statut"] == "essai"
    assert result["code"] == "ABC123"

    state = licence_service.get_state("http://fake")
    assert state["activated"] is True


def test_activate_invalid_code_raises(monkeypatch):
    def fake_post(url, json, timeout):
        return _FakeResponse(404, {"error": "Code d'activation invalide"})

    monkeypatch.setattr(licence_service.requests, "post", fake_post)

    with pytest.raises(licence_service.CodeInvalide):
        licence_service.activate("BADCODE", "http://fake")


def test_activate_offline_raises_request_exception(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(licence_service.requests, "post", fake_post)

    with pytest.raises(requests.RequestException):
        licence_service.activate("ABC123", "http://fake")


# --- gate Flask (before_request) ---------------------------------------------


def test_gate_redirects_to_activation_when_not_activated(app, client):
    app.config["LICENCE_ENFORCEMENT_ENABLED"] = True
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/activation"


def test_gate_returns_403_json_for_blocked_api_calls(app, client):
    app.config["LICENCE_ENFORCEMENT_ENABLED"] = True
    resp = client.get("/api/vehicules")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "licence_invalide"


def test_gate_lets_licence_endpoints_and_activation_page_through(app, client):
    app.config["LICENCE_ENFORCEMENT_ENABLED"] = True
    resp = client.get("/api/licence/status")
    assert resp.status_code == 200

    resp = client.get("/activation")
    assert resp.status_code == 200


def test_gate_disabled_by_default_in_testing(client):
    resp = client.get("/api/setup/status")
    assert resp.status_code == 200
