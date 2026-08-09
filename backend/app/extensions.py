from flask import jsonify
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Authentification requise"}), 401
