def register_blueprints(app):
    from app.api.auth import bp as auth_bp

    app.register_blueprint(auth_bp)
