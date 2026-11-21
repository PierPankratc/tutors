import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import String

from tutors.core.crypto import BlindIndexString, EncryptedString
from tutors.core.database import Base

_new_uuid = getattr(uuid, "uuid7", uuid.uuid4)


class UserRole(enum.StrEnum):
    GUEST = "guest"
    STUDENT = "student"
    TUTOR = "tutor"
    MODERATOR = "moderator"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    # email шифруется AES-256-GCM; поиск при входе выполняется по email_blind_index (HMAC-SHA256)
    email: Mapped[str] = mapped_column(EncryptedString(), nullable=False)
    email_blind_index: Mapped[str] = mapped_column(
        BlindIndexString(),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # TOTP 2FA секрет зашифрован ключом приложения (в БД колонка totp_secret_encrypted)
    totp_secret: Mapped[str | None] = mapped_column(
        "totp_secret_encrypted", EncryptedString(), nullable=True
    )
    is_totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Согласие на обработку ПДн (ст. 9 152-ФЗ) и отметка обезличивания (ст. 21 152-ФЗ)
    pdn_consent_given_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
