import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db

TRIAL_DAYS = 7


def utcnow() -> datetime:
    # Naive UTC partout : les colonnes DateTime (SQLite comme MySQL) perdent le
    # tzinfo au retour de la base, donc comparer avec un datetime "aware" plante.
    return datetime.now(UTC).replace(tzinfo=None)


class StatutLicence(str, enum.Enum):
    ESSAI = "essai"
    ACTIF = "actif"
    SUSPENDU = "suspendu"


class Licence(db.Model):
    __tablename__ = "licences"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    nom_client: Mapped[str] = mapped_column(String(150), nullable=False)
    statut: Mapped[StatutLicence] = mapped_column(
        db.Enum(StatutLicence, values_callable=lambda x: [e.value for e in x]),
        default=StatutLicence.ESSAI,
        nullable=False,
    )
    essai_expire_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    @property
    def est_valide(self) -> bool:
        if self.statut == StatutLicence.SUSPENDU:
            return False
        if self.statut == StatutLicence.ACTIF:
            return True
        if self.essai_expire_le is None:
            return True
        return utcnow() <= self.essai_expire_le

    def __repr__(self) -> str:
        return f"<Licence {self.code} ({self.statut.value})>"
