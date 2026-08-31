import os
import threading
import time

from flask import Flask, jsonify, redirect, request

from app.api import register_blueprints
from app.config import config_by_name
from app.extensions import db, login_manager, migrate
from app.models import User
from app.services import licence as licence_service


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=True, static_folder=None)
    app.config.from_object(config_by_name[config_name])

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    register_blueprints(app)

    from app.web import bp as web_bp

    app.register_blueprint(web_bp)

    from app.cli import register_cli

    register_cli(app)

    @app.before_request
    def _enforce_licence():
        if not app.config.get("LICENCE_ENFORCEMENT_ENABLED"):
            return None

        path = request.path
        if path.startswith("/api/licence") or path.startswith("/static/") or path.startswith("/assets/") or path == "/activation":
            return None

        try:
            state = licence_service.get_state(app.config["LICENCE_SERVER_URL"])
        except Exception:  # noqa: BLE001 - un bug de vérif ne doit jamais bloquer un client
            app.logger.exception("Échec inattendu de la vérification de licence")
            return None

        if not state["blocked"]:
            return None

        if path.startswith("/api/"):
            return jsonify({"error": "licence_invalide", "reason": state["reason"]}), 403
        return redirect("/activation")

    if app.config.get("LICENCE_ENFORCEMENT_ENABLED"):
        _start_licence_watcher(app)

    return app


# Intervalle du contrôle de licence en tâche de fond. Un thread Python n'est pas
# suspendu quand la fenêtre pywebview est réduite (contrairement aux minuteurs JS
# du navigateur embarqué) : le cache local reste donc à jour même app minimisée,
# et un blocage devient effectif dès que l'utilisateur revient sur la fenêtre.
LICENCE_WATCHER_INTERVAL = 300


def _start_licence_watcher(app: Flask) -> None:
    if getattr(app, "_licence_watcher_started", False):
        return
    app._licence_watcher_started = True

    url = app.config["LICENCE_SERVER_URL"]

    def loop() -> None:
        while True:
            time.sleep(LICENCE_WATCHER_INTERVAL)
            try:
                licence_service.get_state(url, force=True)
            except Exception:  # noqa: BLE001
                app.logger.exception("Échec du contrôle de licence en tâche de fond")

    threading.Thread(target=loop, name="licence-watcher", daemon=True).start()
