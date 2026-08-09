from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import TypePieceIdentite


class Client(db.Model):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    prenom: Mapped[str] = mapped_column(String(120), nullable=False)
    telephone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_naissance: Mapped[date | None] = mapped_column(Date, nullable=True)
    type_piece_identite: Mapped[TypePieceIdentite | None] = mapped_column(
        db.Enum(TypePieceIdentite, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    numero_piece_identite: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_identite_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permis_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="client")

    def __repr__(self) -> str:
        return f"<Client {self.prenom} {self.nom}>"
