import os

from flask import Flask

from app.api import register_blueprints
from app.config import config_by_name
from app.extensions import db, login_manager, migrate
from app.models import User


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

    return app
