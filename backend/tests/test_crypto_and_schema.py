import io
from contextlib import redirect_stdout
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.exceptions import InvalidTag
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tutors.core.config import Settings
from tutors.core.crypto import get_encryptor
from tutors.modules.audit.models import AuditLog
from tutors.modules.auth_users.models import User, UserRole
from tutors.modules.profiles.models import TutorProfile, TutorProfileStatus


def test_settings_security_guards() -> None:
    with pytest.raises(ValidationError):
        Settings(CORS_ALLOWED_ORIGINS=["*"])  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        Settings(S3_PRESIGNED_TTL_SECONDS=301)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        Settings(ACCESS_TOKEN_EXPIRE_MINUTES=16)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        Settings(JWT_SECRET_KEY="too_short")  # type: ignore[call-arg]  # noqa: S106


def test_aes256_gcm_encryption_and_blind_index() -> None:
    enc = get_encryptor()
    c1 = enc.encrypt("+79991234567")
    c2 = enc.encrypt("+79991234567")

    assert c1 != c2  # Рандомизированный nonce исключает корреляцию шифртекстов
    assert c1.startswith("v1:")
    assert "+79991234567" not in c1
    assert enc.decrypt(c1) == "+79991234567"

    # Проверка защиты целостности GCM при подмене байта
    tampered = c1[:-2] + ("AA" if c1[-2:] != "AA" else "BB")
    with pytest.raises((InvalidTag, ValueError)):
        enc.decrypt(tampered)

    # Нормализация email для blind index
    assert enc.blind_index("  Ivan@Example.RU ") == enc.blind_index("ivan@example.ru")


async def test_encrypted_pii_stored_as_ciphertext_in_db(db_session: AsyncSession) -> None:
    enc = get_encryptor()
    raw_email = "tutor.ivan@yandex.ru"
    raw_contact = "@ivan_math_tutor"

    user = User(
        email=raw_email,
        email_blind_index=enc.blind_index(raw_email),
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",  # noqa: S106
        role=UserRole.TUTOR,
        pdn_consent_given_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()

    profile = TutorProfile(
        user_id=user.id,
        display_name="Иван П.",
        bio="Подготовка к ЕГЭ по профильной математике",
        price=Decimal("2500.00"),
        experience=7,
        status=TutorProfileStatus.PUBLISHED,
        contact=raw_contact,
    )
    db_session.add(profile)
    await db_session.commit()

    # Чтение напрямую из таблиц без ORM-дешифратора подтверждает шифрование at-rest
    raw_user_row = (
        await db_session.execute(
            text("SELECT email FROM users WHERE email_blind_index = :idx"),
            {"idx": enc.blind_index(raw_email)},
        )
    ).scalar_one()
    assert raw_user_row != raw_email
    assert raw_user_row.startswith("v1:")

    raw_contact_row = (
        await db_session.execute(text("SELECT contact_encrypted FROM tutor_profiles"))
    ).scalar_one()
    assert raw_contact_row != raw_contact
    assert raw_contact_row.startswith("v1:")


async def test_audit_log_is_strictly_append_only(db_session: AsyncSession) -> None:
    entry = AuditLog(
        actor_id=None,
        action="pii.contact.read",
        entity="tutor_profiles",
        entity_id="00000000-0000-0000-0000-000000000001",
        ip="192.0.2.10",
    )
    db_session.add(entry)
    await db_session.commit()
    entry_id = entry.id

    entry.action = "tampered.action"
    with pytest.raises(PermissionError, match="append-only"):
        await db_session.flush()

    await db_session.rollback()

    persisted = await db_session.get(AuditLog, entry_id)
    assert persisted is not None
    await db_session.delete(persisted)
    with pytest.raises(PermissionError, match="append-only"):
        await db_session.flush()


def test_app_factory_cors_configuration() -> None:
    from tutors.main import create_app

    app = create_app()
    assert app.title == "Tutors Marketplace API"


def test_alembic_postgresql16_migration_compiles_cleanly() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://u:p@localhost:5432/db")

    buf = io.StringIO()
    with redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)

    ddl = buf.getvalue()
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in ddl
    assert "USING gin (search_vector)" in ddl
    assert "USING gin (bio gin_trgm_ops)" in ddl
    assert "CREATE TRIGGER trg_audit_log_append_only" in ddl
    assert "CREATE TABLE verification_documents" in ddl
    assert "CREATE TABLE contact_requests" in ddl
