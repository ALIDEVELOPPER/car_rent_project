def register_blueprints(app):
    from app.api.auth import bp as auth_bp
    from app.api.clients import bp as clients_bp
    from app.api.dashboard import bp as dashboard_bp
    from app.api.factures import bp as factures_bp
    from app.api.parametres import bp as parametres_bp
    from app.api.reservations import bp as reservations_bp
    from app.api.setup import bp as setup_bp
    from app.api.uploads import bp as uploads_bp
    from app.api.vehicules import bp as vehicules_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(factures_bp)
    app.register_blueprint(parametres_bp)
    app.register_blueprint(reservations_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(vehicules_bp)
