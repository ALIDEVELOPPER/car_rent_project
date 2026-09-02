from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import Carburant, StatutVehicule, Transmission


class Vehicule(db.Model):
    __tablename__ = "vehicules"

    id: Mapped[int] = mapped_column(primary_key=True)
    marque: Mapped[str] = mapped_column(String(80), nullable=False)
    modele: Mapped[str] = mapped_column(String(80), nullable=False)
    immatriculation: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    categorie: Mapped[str] = mapped_column(String(50), nullable=False)
    annee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    couleur: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kilometrage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carburant: Mapped[Carburant | None] = mapped_column(
        db.Enum(Carburant, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    transmission: Mapped[Transmission | None] = mapped_column(
        db.Enum(Transmission, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    tarif_jour: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    statut: Mapped[StatutVehicule] = mapped_column(
        db.Enum(StatutVehicule, values_callable=lambda x: [e.value for e in x]),
        default=StatutVehicule.DISPONIBLE,
        nullable=False,
    )
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Échéances administratives — servent aux rappels du tableau de bord.
    assurance_expire_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    visite_technique_expire_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    vignette_expire_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    prochaine_vidange_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    prochaine_vidange_km: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="vehicule")

    def __repr__(self) -> str:
        return f"<Vehicule {self.marque} {self.modele} ({self.immatriculation})>"
