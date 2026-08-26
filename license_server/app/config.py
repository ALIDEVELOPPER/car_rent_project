import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'licences.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    ADMIN_TOKEN = "test-admin-token"


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": Config,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
