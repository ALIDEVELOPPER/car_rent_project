from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import ModePaiement, StatutPaiement


class Facture(db.Model):
    __tablename__ = "factures"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"), unique=True, nullable=False
    )
    numero_facture: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    date_emission: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    statut_paiement: Mapped[StatutPaiement] = mapped_column(
        db.Enum(StatutPaiement, values_callable=lambda x: [e.value for e in x]),
        default=StatutPaiement.EN_ATTENTE,
        nullable=False,
    )
    mode_paiement: Mapped[ModePaiement | None] = mapped_column(
        db.Enum(ModePaiement, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    pdf_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    reservation: Mapped["Reservation"] = relationship(back_populates="facture")

    def __repr__(self) -> str:
        return f"<Facture {self.numero_facture}>"
