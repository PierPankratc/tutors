import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tutors.core.crypto import EncryptedString
from tutors.core.database import Base

_new_uuid = getattr(uuid, "uuid7", uuid.uuid4)


class TutorProfileStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_MODERATION = "pending_moderation"
    PUBLISHED = "published"
    SUSPENDED = "suspended"


class ContactRequestStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)


class TutorSubject(Base):
    __tablename__ = "tutor_subjects"

    tutor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutor_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )


class TutorProfile(Base):
    __tablename__ = "tutor_profiles"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("experience >= 0 AND experience <= 80", name="experience_bounds"),
        Index(
            "ix_tutor_profiles_search_vector_gin",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    experience: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_high_education: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[TutorProfileStatus] = mapped_column(
        Enum(
            TutorProfileStatus,
            name="tutor_profile_status_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=TutorProfileStatus.DRAFT,
        nullable=False,
        index=True,
    )
    # В БД колонка contact_encrypted; атрибут отдаёт уже расшифрованное значение
    contact: Mapped[str | None] = mapped_column(
        "contact_encrypted", EncryptedString(), nullable=True
    )

    # В PostgreSQL 16 — GENERATED ALWAYS AS (...) STORED; в SQLite — Text для unit-тестов
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"),
        nullable=True,
    )

    subjects: Mapped[list[Subject]] = relationship(
        secondary="tutor_subjects",
        lazy="selectin",
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint("grade IS NULL OR (grade >= 1 AND grade <= 11)", name="grade_bounds"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(
        "contact_encrypted", EncryptedString(), nullable=True
    )


class ContactRequest(Base):
    """Заявка на обучение: контролирует object-level доступ к контактам репетитора и студента."""

    __tablename__ = "contact_requests"
    __table_args__ = (
        UniqueConstraint("student_id", "tutor_id", name="uq_contact_request_student_tutor"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=_new_uuid,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tutor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutor_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[ContactRequestStatus] = mapped_column(
        Enum(
            ContactRequestStatus,
            name="contact_request_status_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=ContactRequestStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
