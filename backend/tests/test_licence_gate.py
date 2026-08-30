from datetime import timedelta

import pytest
import requests

from app.services import licence as licence_service
from app.services import machine_id


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Cache local isolé + empreinte machine déterministe (pas d'accès registre)."""
    monkeypatch.setattr(licence_service, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(machine_id, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(machine_id, "get_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(machine_id, "get_hostname", lambda: "PC-TEST")
    monkeypatch.setattr(machine_id, "get_os_info", lambda: "TestOS 1.0")
    return tmp_path


def _iso(dt):
    return dt.isoformat()


class FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


def _server_payload(statut="essai", days_to_expire=7, **overrides):
    now = licence_service._now()
    expire = now + timedelta(days=days_to_expire)
    payload = {
        "installation_id": "srv-inst",
        "secret": "srv-secret",
        "statut": statut,
        "essai_expire_le": _iso(expire),
        "bloque_le": _iso(expire + timedelta(days=1)),
        "jours_essai_restants": max(0, days_to_expire),
        "server_time": _iso(now),
    }
    payload.update(overrides)
    return payload


def _mock_post(monkeypatch, handler):
    monkeypatch.setattr(licence_service.requests, "post", handler)


def _write_cache(**overrides):
    now = licence_service._now()
    data = {
        "installation_id": "c-inst",
        "secret": "c-secret",
        "statut": "essai",
        "essai_expire_le": _iso(now + timedelta(days=3)),
        "bloque_le": _iso(now + timedelta(days=4)),
        "jours_essai_restants": 3,
        "server_time_seen_max": _iso(now),
        "last_attempt_at": _iso(now),
        "last_success_at": _iso(now),
    }
    data.update(overrides)
    licence_service._save_cache(data)
    return data


# --- premier lancement ---------------------------------------------------


def test_first_launch_offline_requires_connection(monkeypatch):
    def offline(url, json, timeout):
        raise requests.ConnectionError("offline")

    _mock_post(monkeypatch, offline)
    state = licence_service.get_state("http://fake")
    assert state == {"activated": False, "blocked": True, "reason": "connexion_requise", "cache": None}


def test_first_launch_online_registers_and_starts_trial(monkeypatch):
    def ok(url, json, timeout):
        assert url.endswith("/register")
        assert json["machine_fingerprint"] == "test-fingerprint"
        return FakeResp(200, _server_payload())

    _mock_post(monkeypatch, ok)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False
    assert state["reason"] == "essai"
    assert state["cache"]["secret"] == "srv-secret"
    # cache écrit + copie de secours de l'installation_id
    assert (licence_service._cache_path()).exists()
    assert licence_service._recover_installation_id() == "srv-inst"


# --- cache corrompu ----------------------------------------------------


def test_corrupt_cache_falls_back_to_backup(monkeypatch):
    _write_cache(statut="actif", essai_expire_le=None, bloque_le=None)
    _write_cache(statut="actif", essai_expire_le=None, bloque_le=None)  # crée le .bak
    licence_service._cache_path().write_text("{{ corrompu")

    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False
    assert state["cache"]["statut"] == "actif"


# --- essai / grâce / expiration --------------------------------------


def test_trial_in_progress_not_blocked(monkeypatch):
    _write_cache()
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False
    assert state["reason"] == "essai"


def test_trial_expired_within_grace_not_blocked(monkeypatch):
    now = licence_service._now()
    _write_cache(
        essai_expire_le=_iso(now - timedelta(hours=2)),
        bloque_le=_iso(now + timedelta(hours=22)),
        last_success_at=_iso(now - timedelta(hours=3)),
    )
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False
    assert state["reason"] == "essai_grace"


def test_trial_confirmed_expired_blocks(monkeypatch):
    now = licence_service._now()
    _write_cache(
        essai_expire_le=_iso(now - timedelta(days=2)),
        bloque_le=_iso(now - timedelta(days=1)),
        confirmed_expired=True,
    )
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "essai_expire"


def test_trial_offline_past_grace_but_within_offline_tolerance(monkeypatch):
    now = licence_service._now()
    _write_cache(
        essai_expire_le=_iso(now - timedelta(days=2)),
        bloque_le=_iso(now - timedelta(days=1)),
        last_success_at=_iso(now - timedelta(days=5)),  # dernier contact AVANT expiration
        last_attempt_at=_iso(now),
    )
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False  # tolérance hors-ligne (OFFLINE_GRACE_DAYS)


def test_trial_offline_past_all_tolerance_blocks(monkeypatch):
    now = licence_service._now()
    _write_cache(
        essai_expire_le=_iso(now - timedelta(days=licence_service.OFFLINE_GRACE_DAYS + 2)),
        bloque_le=_iso(now - timedelta(days=licence_service.OFFLINE_GRACE_DAYS + 1)),
        last_success_at=_iso(now - timedelta(days=20)),
        last_attempt_at=_iso(now),
    )
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "verification_impossible"


# --- suspendu / actif -------------------------------------------------


def test_suspended_blocks(monkeypatch):
    _write_cache(statut="suspendu")
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "suspendu"


def test_active_not_blocked(monkeypatch):
    _write_cache(statut="actif", essai_expire_le=None, bloque_le=None)
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False


def test_active_offline_too_long_requires_recheck(monkeypatch):
    now = licence_service._now()
    _write_cache(
        statut="actif",
        essai_expire_le=None,
        bloque_le=None,
        last_success_at=_iso(now - timedelta(days=licence_service.MAX_OFFLINE_ACTIF_DAYS + 1)),
        server_time_seen_max=_iso(now - timedelta(days=licence_service.MAX_OFFLINE_ACTIF_DAYS + 1)),
    )
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True
    assert state["reason"] == "reverification_requise"


# --- anti triche horloge -------------------------------------------


def test_clock_rollback_does_not_extend_trial(monkeypatch):
    now = licence_service._now()
    # Essai + grâce + tolérance hors-ligne tous dépassés selon le temps serveur
    # déjà vu ; mais l'horloge locale est reculée de 30 jours.
    _write_cache(
        essai_expire_le=_iso(now - timedelta(days=10)),
        bloque_le=_iso(now - timedelta(days=9)),
        server_time_seen_max=_iso(now),
        last_success_at=_iso(now - timedelta(days=15)),
        last_attempt_at=_iso(now),
    )
    monkeypatch.setattr(licence_service, "_now", lambda: now - timedelta(days=30))
    monkeypatch.setattr(licence_service, "_heartbeat", lambda url, cache: None)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is True

    # Sans la borne server_time_seen_max, l'horloge reculée rouvrirait l'essai.
    cache_no_bound = _write_cache(
        essai_expire_le=_iso(now - timedelta(days=10)),
        bloque_le=_iso(now - timedelta(days=9)),
        server_time_seen_max=None,
        last_success_at=_iso(now - timedelta(days=15)),
        last_attempt_at=_iso(now),
    )
    assert licence_service._verdict(cache_no_bound)["blocked"] is False


# --- back-off réseau ----------------------------------------------


def test_recent_failed_attempt_skips_network(monkeypatch):
    now = licence_service._now()
    _write_cache(
        essai_expire_le=_iso(now - timedelta(hours=1)),
        bloque_le=_iso(now + timedelta(hours=23)),
        last_success_at=_iso(now - timedelta(days=2)),
        last_attempt_at=_iso(now - timedelta(minutes=5)),  # < RETRY_INTERVAL
    )

    def fail(url, cache):
        raise AssertionError("ne devrait pas être appelé")

    monkeypatch.setattr(licence_service, "_heartbeat", fail)
    state = licence_service.get_state("http://fake")
    assert state["blocked"] is False


def test_heartbeat_401_triggers_reregister(monkeypatch):
    _write_cache(last_success_at=_iso(licence_service._now() - timedelta(days=2)))
    calls = []

    def handler(url, json, timeout):
        calls.append(url)
        if url.endswith("/heartbeat"):
            return FakeResp(401, {"error": "secret invalide"})
        return FakeResp(200, _server_payload(statut="actif", days_to_expire=0,
                                             essai_expire_le=_iso(licence_service._now()),
                                             bloque_le=_iso(licence_service._now())))

    _mock_post(monkeypatch, handler)
    state = licence_service.get_state("http://fake", force=True)
    assert any(u.endswith("/register") for u in calls)
    assert state["cache"]["statut"] == "actif"


# --- gate Flask ----------------------------------------------------


def test_gate_redirects_to_activation_when_blocked(app, client, monkeypatch):
    app.config["LICENCE_ENFORCEMENT_ENABLED"] = True
    monkeypatch.setattr(
        licence_service, "get_state",
        lambda url, force=False: {"activated": True, "blocked": True, "reason": "suspendu", "cache": {}},
    )
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/activation"


def test_gate_returns_403_json_for_api(app, client, monkeypatch):
    app.config["LICENCE_ENFORCEMENT_ENABLED"] = True
    monkeypatch.setattr(
        licence_service, "get_state",
        lambda url, force=False: {"activated": True, "blocked": True, "reason": "essai_expire", "cache": {}},
    )
    resp = client.get("/api/vehicules")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "licence_invalide"


def test_gate_lets_licence_status_and_activation_through(app, client, monkeypatch):
    app.config["LICENCE_ENFORCEMENT_ENABLED"] = True
    monkeypatch.setattr(
        licence_service, "get_state",
        lambda url, force=False: {"activated": True, "blocked": True, "reason": "suspendu", "cache": {}},
    )
    assert client.get("/api/licence/status").status_code == 200
    assert client.get("/activation").status_code == 200


def test_gate_disabled_by_default_in_testing(client):
    assert client.get("/api/setup/status").status_code == 200
