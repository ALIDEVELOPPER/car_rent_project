import enum
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db

# Durée de l'essai gratuit, et jours de grâce après expiration pendant lesquels
# l'app cliente fonctionne encore (avec un bandeau d'avertissement) avant blocage.
TRIAL_DAYS = 7
GRACE_DAYS = 1


def utcnow() -> datetime:
    # Naive UTC partout : les colonnes DateTime (SQLite comme MySQL) perdent le
    # tzinfo au retour de la base, donc comparer avec un datetime "aware" plante.
    return datetime.now(UTC).replace(tzinfo=None)


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


class StatutInstallation(str, enum.Enum):
    ESSAI = "essai"       # essai gratuit en cours (ou dans sa période de grâce)
    ACTIF = "actif"       # abonnement payé, validé par l'éditeur
    SUSPENDU = "suspendu"  # bloqué manuellement par l'éditeur


class Installation(db.Model):
    """Une installation de l'app métier sur un poste client.

    Créée automatiquement au premier lancement de l'app (endpoint /register).
    L'éditeur approuve (→ actif) ou bloque (→ suspendu) depuis la console admin.
    """

    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identifiant généré par l'app (UUID), stable pour une installation donnée.
    installation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Empreinte matérielle hachée : permet de repérer un même poste ré-enregistré
    # (ex. client qui supprime son cache local pour tenter un nouvel essai).
    machine_fingerprint: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    # Jeton remis à l'app à l'enregistrement, exigé pour les heartbeats.
    secret: Mapped[str] = mapped_column(String(64), nullable=False, default=generate_secret)

    # Métadonnées d'affichage (renseignées par l'app).
    nom_agence: Mapped[str | None] = mapped_column(String(150), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(150), nullable=True)
    os_info: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Champs de gestion commerciale (renseignés par l'éditeur).
    email_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str | None] = mapped_column(String(60), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    statut: Mapped[StatutInstallation] = mapped_column(
        db.Enum(StatutInstallation, values_callable=lambda x: [e.value for e in x]),
        default=StatutInstallation.ESSAI,
        nullable=False,
    )
    essai_expire_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    @property
    def bloque_le(self) -> datetime:
        """Date de blocage effectif : fin d'essai + période de grâce."""
        return self.essai_expire_le + timedelta(days=GRACE_DAYS)

    @property
    def est_valide(self) -> bool:
        if self.statut == StatutInstallation.SUSPENDU:
            return False
        if self.statut == StatutInstallation.ACTIF:
            return True
        return utcnow() <= self.bloque_le

    @property
    def jours_essai_restants(self) -> int:
        if self.statut != StatutInstallation.ESSAI:
            return 0
        delta = self.essai_expire_le - utcnow()
        if delta.total_seconds() <= 0:
            return 0
        # Arrondi au jour supérieur : 0j23h => "1 jour restant".
        return -(-int(delta.total_seconds()) // 86400)

    def touch(self) -> None:
        self.last_seen_at = utcnow()

    def start_trial(self) -> None:
        now = utcnow()
        self.registered_at = now
        self.essai_expire_le = now + timedelta(days=TRIAL_DAYS)
        self.statut = StatutInstallation.ESSAI

    def approve(self) -> None:
        self.statut = StatutInstallation.ACTIF
        self.activated_at = utcnow()
        self.suspended_at = None

    def block(self) -> None:
        self.statut = StatutInstallation.SUSPENDU
        self.suspended_at = utcnow()

    def __repr__(self) -> str:
        return f"<Installation {self.installation_id[:8]} ({self.statut.value})>"
