from datetime import UTC, datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.enums import RoleUser


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleUser] = mapped_column(
        db.Enum(RoleUser, values_callable=lambda x: [e.value for e in x]),
        default=RoleUser.EMPLOYE,
        nullable=False,
    )
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def set_password(self, mot_de_passe: str) -> None:
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def check_password(self, mot_de_passe: str) -> bool:
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    @property
    def is_active(self) -> bool:
        return self.actif

    @property
    def is_admin(self) -> bool:
        return self.role == RoleUser.ADMIN

    def __repr__(self) -> str:
        return f"<User {self.email}>"
