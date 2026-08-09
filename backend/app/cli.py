import click

from app.extensions import db
from app.models import User
from app.models.enums import RoleUser


def register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--nom", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--mot-de-passe", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(nom, email, mot_de_passe):
        """Crée un compte administrateur (bootstrap du tout premier utilisateur)."""
        email = email.strip().lower()
        existing = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        if existing is not None:
            click.echo(f"Un utilisateur existe déjà avec l'email {email}")
            return

        user = User(nom=nom, email=email, role=RoleUser.ADMIN)
        user.set_password(mot_de_passe)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrateur créé : {email}")
