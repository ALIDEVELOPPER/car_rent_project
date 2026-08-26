import os
import secrets
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from app.paths import get_app_data_dir, is_frozen

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = get_app_data_dir()

if is_frozen():
    load_dotenv(Path(sys._MEIPASS) / ".env")
else:
    load_dotenv(BASE_DIR / ".env")


def _load_or_create_secret_key() -> str:
    env_value = os.environ.get("SECRET_KEY")
    if env_value:
        return env_value

    secret_file = INSTANCE_DIR / "secret_key"
    if secret_file.exists():
        return secret_file.read_text().strip()

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    secret_file.write_text(key)
    return key


class Config:
    SECRET_KEY = _load_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = (
        str(INSTANCE_DIR / "uploads")
        if is_frozen()
        else str(BASE_DIR / os.environ.get("UPLOAD_FOLDER", "app/static_uploads"))
    )
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", 10)) * 1024 * 1024
    CURRENCY_LABEL = os.environ.get("CURRENCY_LABEL", "MAD")

    # URL du serveur central de licences (license_server/), utilisée pour l'activation
    # et la revérification au bout de l'essai. Le verrou n'est actif qu'en ProductionConfig
    # (l'exécutable packagé) : ni les tests, ni le dev quotidien via `flask run` n'y sont soumis.
    LICENCE_SERVER_URL = os.environ.get("LICENCE_SERVER_URL", "http://127.0.0.1:5100")
    LICENCE_ENFORCEMENT_ENABLED = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "testing-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Dossier temporaire dédié : évite que les tests d'upload polluent app/static_uploads
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix="car_rent_test_uploads_")


class ProductionConfig(Config):
    DEBUG = False
    LICENCE_ENFORCEMENT_ENABLED = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
