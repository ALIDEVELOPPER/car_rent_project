from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import StatutCaution, StatutReservation


class Reservation(db.Model):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    vehicule_id: Mapped[int] = mapped_column(ForeignKey("vehicules.id"), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[StatutReservation] = mapped_column(
        db.Enum(StatutReservation, values_callable=lambda x: [e.value for e in x]),
        default=StatutReservation.EN_ATTENTE,
        nullable=False,
    )
    # Copié depuis Vehicule.tarif_jour à la création : un changement de tarif après coup
    # ne doit pas modifier le montant d'une réservation déjà passée.
    prix_jour_applique: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    montant_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    caution: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"), server_default="0")
    caution_statut: Mapped[StatutCaution] = mapped_column(
        db.Enum(StatutCaution, values_callable=lambda x: [e.value for e in x]),
        default=StatutCaution.NON_RECUE, server_default="non_recue", nullable=False,
    )
    caution_retenue: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    caution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    lieu_prise_en_charge: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    client: Mapped["Client"] = relationship(back_populates="reservations")
    vehicule: Mapped["Vehicule"] = relationship(back_populates="reservations")
    agent: Mapped["User | None"] = relationship()
    facture: Mapped["Facture"] = relationship(back_populates="reservation", uselist=False)

    def __repr__(self) -> str:
        return f"<Reservation {self.id} client={self.client_id} vehicule={self.vehicule_id}>"
