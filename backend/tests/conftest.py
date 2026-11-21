import base64
import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Тестовые ключи задаются через окружение ДО инициализации Settings
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_with_minimum_32_bytes_len!")
os.environ.setdefault("CSRF_SECRET_KEY", "test_csrf_secret_key_with_minimum_32_bytes_len!")
os.environ.setdefault(
    "PII_ENCRYPTION_KEY",
    base64.urlsafe_b64encode(b"0123456789abcdef0123456789abcdef").decode("ascii"),
)
os.environ.setdefault("PII_BLIND_INDEX_KEY", "test_blind_index_hmac_key_32_bytes_minimum!!")
os.environ.setdefault("S3_BUCKET_DIPLOMAS", "test-private-diplomas")
os.environ.setdefault("S3_ACCESS_KEY_ID", "test_access_key")
os.environ.setdefault("S3_SECRET_ACCESS_KEY", "test_secret_key")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')

from tutors.core.models_registry import Base  # noqa: E402


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
