from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


# Table à une seule ligne : les coordonnées de l'agence affichées sur les factures.
class Agence(db.Model):
    __tablename__ = "agence"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mentions_legales: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions_contrat: Mapped[str | None] = mapped_column(Text, nullable=True)
    langue: Mapped[str] = mapped_column(String(2), nullable=False, default="fr", server_default="fr")

    # Identifiants légaux (Maroc) — affichés sur factures et contrats.
    ice: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rc: Mapped[str | None] = mapped_column(String(30), nullable=True)
    identifiant_fiscal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    patente: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # TVA : beaucoup de petites agences ne sont pas assujetties.
    tva_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    taux_tva: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("20"), server_default="20"
    )

    def __repr__(self) -> str:
        return f"<Agence {self.nom}>"
