import sqlite3

from flask import jsonify
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Authentification requise"}), 401


# SQLite n'applique pas les contraintes FOREIGN KEY par défaut ; sans ce pragma,
# supprimer un client avec des réservations laisserait des lignes orphelines.
@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
