"""Vérification de licence pour l'app packagée (voir license_server/).

Modèle : au premier lancement, l'app s'enregistre automatiquement auprès du
serveur central (empreinte machine + identifiant d'installation) et démarre un
essai de 7 jours. Ensuite elle refait un « heartbeat » périodique pour détecter
approbation / blocage décidés par l'éditeur. Entre deux vérifications, lecture du
cache local uniquement (rapide, fonctionne hors-ligne). Aucune donnée métier
n'est envoyée : seulement l'état de la licence.
"""
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from app.paths import get_app_data_dir
from app.services import machine_id

# Tolérance hors-ligne après expiration de l'essai, si le serveur n'a jamais pu
# confirmer (PC client sans internet). Au-delà : blocage.
OFFLINE_GRACE_DAYS = 3
# Un client "actif" (payé) qui reste hors-ligne trop longtemps doit se
# reconnecter au moins une fois (anti-abus : payer 1 mois puis rester offline).
MAX_OFFLINE_ACTIF_DAYS = 30
# Fréquence de revérification en ligne quand tout va bien.
RECHECK_INTERVAL = timedelta(hours=24)
# Anti-martèlement : délai minimal entre deux tentatives réseau ratées.
RETRY_INTERVAL = timedelta(hours=1)
REQUEST_TIMEOUT = 6


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse(iso_value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso_value) if iso_value else None
    except (TypeError, ValueError):
        return None


# --- Cache local ------------------------------------------------------------


def _cache_path() -> Path:
    return get_app_data_dir() / "licence.json"


def _backup_path() -> Path:
    return get_app_data_dir() / "licence.json.bak"


def _id_path() -> Path:
    # Copie de secours de l'installation_id, pour se remettre d'un cache corrompu.
    return get_app_data_dir() / "install.dat"


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _load_cache() -> dict | None:
    return _read_json(_cache_path()) or _read_json(_backup_path())


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".licence-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _save_cache(data: dict) -> None:
    text = json.dumps(data)
    current = _cache_path()
    if current.exists():
        try:
            _atomic_write(_backup_path(), current.read_text())
        except OSError:
            pass
    _atomic_write(current, text)
    if data.get("installation_id"):
        try:
            _atomic_write(_id_path(), data["installation_id"])
        except OSError:
            pass


def _recover_installation_id() -> str | None:
    try:
        value = _id_path().read_text().strip()
        return value or None
    except OSError:
        return None


# --- Identité --------------------------------------------------------------


def _new_installation_id() -> str:
    import uuid

    return uuid.uuid4().hex


def _identity(cache: dict | None) -> dict:
    installation_id = (
        (cache or {}).get("installation_id")
        or _recover_installation_id()
        or _new_installation_id()
    )
    return {
        "installation_id": installation_id,
        "machine_fingerprint": machine_id.get_fingerprint(),
        "hostname": machine_id.get_hostname(),
        "os_info": machine_id.get_os_info(),
    }


# --- Appels réseau --------------------------------------------------------


def _server_url(base: str) -> str:
    return base.rstrip("/")


def _merge_response(payload: dict, installation_id: str, previous: dict | None) -> dict:
    data = dict(previous or {})
    data.update(payload)
    data["installation_id"] = payload.get("installation_id") or installation_id
    data["last_attempt_at"] = _now().isoformat()
    data["last_success_at"] = _now().isoformat()

    # server_time_seen_max : borne anti-recul d'horloge.
    server_time = _parse(payload.get("server_time"))
    previous_max = _parse((previous or {}).get("server_time_seen_max"))
    seen_max = max(filter(None, [server_time, previous_max, _now()]))
    data["server_time_seen_max"] = seen_max.isoformat()

    # Si le serveur a confirmé après l'expiration, on le note (verdict fiable).
    expire = _parse(payload.get("essai_expire_le"))
    if payload.get("statut") == "essai" and expire is not None and server_time and server_time >= expire:
        data["confirmed_expired"] = True
    elif payload.get("statut") != "essai":
        data.pop("confirmed_expired", None)
    return data


def register(server_url: str, cache: dict | None = None) -> dict:
    """Enregistre l'installation auprès du serveur central. Lève
    requests.RequestException si le serveur est injoignable."""
    ident = _identity(cache)
    resp = requests.post(
        f"{_server_url(server_url)}/register",
        json=ident,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = _merge_response(resp.json(), ident["installation_id"], cache)
    data.setdefault("hostname", ident["hostname"])
    data.setdefault("os_info", ident["os_info"])
    _save_cache(data)
    return data


def _heartbeat(server_url: str, cache: dict) -> dict | None:
    installation_id = cache.get("installation_id")
    secret = cache.get("secret")
    if not installation_id or not secret:
        return None
    try:
        resp = requests.post(
            f"{_server_url(server_url)}/heartbeat",
            json={"installation_id": installation_id, "secret": secret},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 401:
            # Secret rejeté : on retente un register (récupère l'installation par empreinte).
            return register(server_url, cache)
        resp.raise_for_status()
    except requests.RequestException:
        updated = dict(cache)
        updated["last_attempt_at"] = _now().isoformat()
        _save_cache(updated)
        return None

    data = _merge_response(resp.json(), installation_id, cache)
    _save_cache(data)
    return data


# --- Décision -------------------------------------------------------------


def _effective_now(cache: dict) -> datetime:
    """max(horloge locale, dernier temps serveur vu) : reculer l'horloge locale
    ne permet pas de prolonger l'essai."""
    seen_max = _parse(cache.get("server_time_seen_max"))
    return max(filter(None, [_now(), seen_max]))


def _should_refresh(cache: dict, force: bool) -> bool:
    if force:
        return True

    last_attempt = _parse(cache.get("last_attempt_at"))
    last_success = _parse(cache.get("last_success_at"))
    now = _now()

    # Jamais contacté avec succès -> essayer (sauf si on vient d'essayer).
    if last_success is None:
        return last_attempt is None or now - last_attempt >= RETRY_INTERVAL

    # Essai théoriquement fini mais pas encore confirmé -> revérifier, avec back-off.
    expire = _parse(cache.get("essai_expire_le"))
    if (
        cache.get("statut") == "essai"
        and expire is not None
        and _effective_now(cache) >= expire
        and not cache.get("confirmed_expired")
    ):
        return last_attempt is None or now - last_attempt >= RETRY_INTERVAL

    return now - last_success >= RECHECK_INTERVAL


def _verdict(cache: dict) -> dict:
    statut = cache.get("statut")
    now = _effective_now(cache)
    last_success = _parse(cache.get("last_success_at"))
    days_left = cache.get("jours_essai_restants")

    if statut == "suspendu":
        return {"activated": True, "blocked": True, "reason": "suspendu", "cache": cache}

    if statut == "actif":
        if last_success is not None and now - last_success > timedelta(days=MAX_OFFLINE_ACTIF_DAYS):
            return {"activated": True, "blocked": True, "reason": "reverification_requise", "cache": cache}
        return {"activated": True, "blocked": False, "reason": None, "cache": cache}

    # --- essai ---
    expire = _parse(cache.get("essai_expire_le"))
    bloque = _parse(cache.get("bloque_le"))

    if expire is None:
        return {"activated": True, "blocked": False, "reason": "essai", "cache": cache}

    if now <= expire:
        return {"activated": True, "blocked": False, "reason": "essai", "cache": cache}

    # Essai expiré : on est dans la fenêtre de grâce jusqu'à `bloque_le`.
    if bloque is not None and now <= bloque:
        return {"activated": True, "blocked": False, "reason": "essai_grace", "cache": cache}

    # Au-delà de la grâce.
    if cache.get("confirmed_expired"):
        return {"activated": True, "blocked": True, "reason": "essai_expire", "cache": cache}

    # Jamais reconfirmé depuis l'expiration (hors-ligne) : tolérance supplémentaire.
    if last_success is not None and last_success >= expire:
        return {"activated": True, "blocked": True, "reason": "essai_expire", "cache": cache}

    if now <= expire + timedelta(days=OFFLINE_GRACE_DAYS):
        return {"activated": True, "blocked": False, "reason": "essai_grace", "cache": cache}

    return {"activated": True, "blocked": True, "reason": "verification_impossible", "cache": cache}


def get_state(licence_server_url: str, force: bool = False) -> dict:
    """Renvoie {'activated': bool, 'blocked': bool, 'reason': str|None, 'cache': dict|None}.

    reason possibles : None (ok), 'essai' (essai en cours), 'essai_grace' (essai
    fini, période de grâce), 'essai_expire', 'suspendu', 'verification_impossible',
    'reverification_requise', 'connexion_requise' (1er lancement hors-ligne).
    """
    cache = _load_cache()

    if cache is None or not cache.get("secret"):
        try:
            cache = register(licence_server_url, cache)
        except requests.RequestException:
            return {"activated": False, "blocked": True, "reason": "connexion_requise", "cache": None}

    if _should_refresh(cache, force):
        fresh = _heartbeat(licence_server_url, cache)
        if fresh is not None:
            cache = fresh

    return _verdict(cache)
