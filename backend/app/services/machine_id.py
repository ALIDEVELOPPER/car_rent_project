"""Empreinte matérielle du poste, pour lier une installation à une machine.

Objectif : repérer côté serveur qu'une même machine se ré-enregistre (ex. client
qui supprime son cache local pour tenter un nouvel essai). Ce n'est pas une
protection anti-crack forte — juste un identifiant raisonnablement stable.
"""
import hashlib
import platform
import subprocess
import uuid
from pathlib import Path

from app.paths import get_app_data_dir


def _windows_machine_guid() -> str | None:
    try:
        import winreg  # type: ignore

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return value or None
    except OSError:
        return None


def _macos_platform_uuid() -> str | None:
    try:
        out = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                return line.split('"')[-2]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _linux_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            value = Path(path).read_text().strip()
            if value:
                return value
        except OSError:
            continue
    return None


def _fallback_id() -> str:
    """Dernier recours : un identifiant aléatoire persistant dans le dossier de données."""
    path = get_app_data_dir() / "machine.id"
    try:
        existing = path.read_text().strip()
        if existing:
            return existing
    except OSError:
        pass
    value = uuid.uuid4().hex
    try:
        path.write_text(value)
    except OSError:
        pass
    return value


def _raw_machine_id() -> str:
    system = platform.system()
    if system == "Windows":
        return _windows_machine_guid() or _fallback_id()
    if system == "Darwin":
        return _macos_platform_uuid() or _fallback_id()
    if system == "Linux":
        return _linux_machine_id() or _fallback_id()
    return _fallback_id()


def get_fingerprint() -> str:
    """Empreinte hachée (le hash évite d'exposer l'ID matériel brut au serveur)."""
    raw = f"{_raw_machine_id()}|{platform.node()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_os_info() -> str:
    return f"{platform.system()} {platform.release()}".strip()


def get_hostname() -> str:
    return platform.node() or "inconnu"
