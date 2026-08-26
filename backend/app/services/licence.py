"""Vérification de licence pour l'app packagée (voir license_server/).

L'app métier reste 100% locale (aucune donnée client n'est envoyée au serveur
central) : ce module ne fait que activer/revérifier un code de licence, et
met en cache le dernier état connu pour fonctionner hors-ligne le reste du temps.
"""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from app.paths import get_app_data_dir

GRACE_DAYS = 3
RECHECK_INTERVAL = timedelta(hours=24)
REQUEST_TIMEOUT = 5


class CodeInvalide(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _cache_path() -> Path:
    return get_app_data_dir() / "licence.json"


def _load_cache() -> dict | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(data: dict) -> None:
    _cache_path().write_text(json.dumps(data))


def _server_url(licence_server_url: str) -> str:
    return licence_server_url.rstrip("/")


def activate(code: str, licence_server_url: str) -> dict:
    """Active un code auprès du serveur central. Lève CodeInvalide si le code
    n'existe pas, ou requests.RequestException si le serveur est injoignable."""
    resp = requests.post(f"{_server_url(licence_server_url)}/activate", json={"code": code}, timeout=REQUEST_TIMEOUT)
    if resp.status_code == 404:
        raise CodeInvalide("Code d'activation invalide")
    resp.raise_for_status()

    data = resp.json()
    data["code"] = code
    data["last_checked_at"] = _now().isoformat()
    _save_cache(data)
    return data


def _refresh(code: str, licence_server_url: str) -> dict | None:
    try:
        resp = requests.get(
            f"{_server_url(licence_server_url)}/status", params={"code": code}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    data = resp.json()
    data["code"] = code
    data["last_checked_at"] = _now().isoformat()
    _save_cache(data)
    return data


def _parse(iso_value: str | None) -> datetime | None:
    return datetime.fromisoformat(iso_value) if iso_value else None


def _should_attempt_refresh(cache: dict, force: bool) -> bool:
    if force:
        return True

    expire = _parse(cache.get("essai_expire_le"))
    if cache.get("statut") == "essai" and expire is not None and _now() >= expire:
        return True

    last_checked = _parse(cache.get("last_checked_at"))
    if last_checked is None:
        return True
    return _now() - last_checked >= RECHECK_INTERVAL


def get_state(licence_server_url: str, force: bool = False) -> dict:
    """Renvoie {'activated': bool, 'blocked': bool, 'reason': str | None, 'cache': dict | None}.

    Revérifie auprès du serveur central périodiquement (au moins une fois par
    jour, ou immédiatement si l'essai vient d'expirer, ou si `force=True`),
    pour que suspension et réactivation soient détectées même sans que le
    client ne réinstalle l'app. Le reste du temps, lecture du cache local
    uniquement (rapide, fonctionne hors-ligne).
    """
    cache = _load_cache()
    if cache is None:
        return {"activated": False, "blocked": True, "reason": "activation_requise", "cache": None}

    if _should_attempt_refresh(cache, force):
        fresh = _refresh(cache.get("code"), licence_server_url)
        if fresh is not None:
            cache = fresh

    statut = cache.get("statut")

    if statut == "actif":
        return {"activated": True, "blocked": False, "reason": None, "cache": cache}

    if statut == "suspendu":
        return {"activated": True, "blocked": True, "reason": "suspendu", "cache": cache}

    # essai
    expire = _parse(cache.get("essai_expire_le"))
    if expire is None or _now() <= expire:
        return {"activated": True, "blocked": False, "reason": None, "cache": cache}

    last_checked = _parse(cache.get("last_checked_at"))
    if last_checked is not None and last_checked >= expire:
        # Le serveur a confirmé après l'expiration que ce n'est pas payé : verdict fiable.
        return {"activated": True, "blocked": True, "reason": "essai_expire", "cache": cache}

    # Aucun contact réussi avec le serveur depuis l'expiration (hors-ligne) : tolérance de grâce.
    grace_deadline = expire + timedelta(days=GRACE_DAYS)
    if _now() <= grace_deadline:
        return {"activated": True, "blocked": False, "reason": None, "cache": cache}

    return {"activated": True, "blocked": True, "reason": "verification_impossible", "cache": cache}
