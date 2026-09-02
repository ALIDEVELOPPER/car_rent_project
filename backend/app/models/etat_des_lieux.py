from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import NiveauCarburant, TypeEtatDesLieux


class EtatDesLieux(db.Model):
    """État des lieux d'un véhicule au départ ou au retour d'une location."""

    __tablename__ = "etats_des_lieux"
    __table_args__ = (UniqueConstraint("reservation_id", "type", name="uq_etat_reservation_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"), nullable=False, index=True)
    type: Mapped[TypeEtatDesLieux] = mapped_column(
        db.Enum(TypeEtatDesLieux, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    date_effectue: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    kilometrage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    niveau_carburant: Mapped[NiveauCarburant | None] = mapped_column(
        db.Enum(NiveauCarburant, values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    degats: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    # URLs de photos, une par ligne.
    photos: Mapped[str | None] = mapped_column(Text, nullable=True)

    reservation: Mapped["Reservation"] = relationship(back_populates="etats_des_lieux")

    @property
    def photos_liste(self) -> list[str]:
        return [p for p in (self.photos or "").splitlines() if p.strip()]

    def ajouter_photo(self, url: str) -> None:
        photos = self.photos_liste
        photos.append(url)
        self.photos = "\n".join(photos)

    def __repr__(self) -> str:
        return f"<EtatDesLieux {self.type.value} resa={self.reservation_id}>"
