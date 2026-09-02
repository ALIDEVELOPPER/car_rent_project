from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import TypeDepense


class DepenseVehicule(db.Model):
    """Charge liée à un véhicule (achat, assurance, entretien, réparation,
    traite de crédit…). Sert au calcul de la marge nette par véhicule."""

    __tablename__ = "depenses_vehicule"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicule_id: Mapped[int] = mapped_column(
        ForeignKey("vehicules.id"), nullable=False, index=True
    )
    type: Mapped[TypeDepense] = mapped_column(
        db.Enum(TypeDepense, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    date_depense: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    vehicule: Mapped["Vehicule"] = relationship(back_populates="depenses")

    def __repr__(self) -> str:
        return f"<DepenseVehicule {self.type.value} {self.montant} vehicule={self.vehicule_id}>"
