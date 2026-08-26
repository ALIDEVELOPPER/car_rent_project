import os
from pathlib import Path

from flask import Flask, send_from_directory

from app.config import config_by_name
from app.extensions import db

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)

    from app.api import admin_bp, public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    @app.get("/")
    @app.get("/admin")
    def admin_page():
        return send_from_directory(FRONTEND_DIR, "admin.html")

    @app.get("/vendor/<path:filename>")
    def vendor(filename):
        return send_from_directory(FRONTEND_DIR / "vendor", filename)

    with app.app_context():
        db.create_all()

    return app
