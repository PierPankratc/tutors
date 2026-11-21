import logging
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr, ValidationError
from tutors.core.config import get_settings
from tutors.core.errors import AppError
from tutors.core.logging import SensitiveDataFilter
from tutors.core.rate_limit import InMemoryRateLimitBackend, RateLimiter
from tutors.core.redis import InMemorySessionStore
from tutors.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    csrf_tokens_match,
    decode_token,
    generate_csrf_token,
    generate_totp_secret,
    hash_password,
    verify_csrf_token,
    verify_password,
    verify_totp,
)
from tutors.core.storage import InMemoryObjectStorage, validate_diploma_upload
from tutors.modules.auth_users.schemas import RegisterRequest


def test_argon2id_hash_and_verify() -> None:
    password = "StrongPassw0rd!2026"  # noqa: S105 - тестовый пароль
    hashed = hash_password(password)
    assert hashed.startswith("$argon2id$")
    assert password not in hashed
    assert verify_password(hashed, password) == (True, False)
    assert verify_password(hashed, "wrong-password") == (False, False)


def test_jwt_type_isolation_and_tampering() -> None:
    settings = get_settings()
    user_id = uuid.uuid4()
    access, expires_in = create_access_token(settings, user_id=user_id, role="student")
    refresh, jti, family, ttl = create_refresh_token(settings, user_id=user_id, role="student")

    assert expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert ttl == settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    assert decode_token(settings, access, expected_type="access")["sub"] == str(user_id)
    assert decode_token(settings, refresh, expected_type="refresh")["jti"] == jti
    assert family

    with pytest.raises(InvalidTokenError):
        decode_token(settings, access, expected_type="refresh")

    tampered = access[:-1] + ("A" if access[-1] != "A" else "B")
    with pytest.raises(InvalidTokenError):
        decode_token(settings, tampered, expected_type="access")

    expired = jwt.encode(
        {
            "sub": str(user_id),
            "role": "student",
            "type": "access",
            "jti": "x",
            "iss": "tutors-api",
            "aud": "tutors-web",
            "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(settings, expired, expected_type="access")


def test_csrf_signing_and_matching() -> None:
    settings = get_settings()
    token = generate_csrf_token(settings)
    assert verify_csrf_token(settings, token)
    assert not verify_csrf_token(settings, token + "x")
    assert csrf_tokens_match(token, token)
    assert not csrf_tokens_match(token, token[:-1])


def test_totp_verification() -> None:
    import pyotp

    secret = generate_totp_secret()
    assert verify_totp(secret, pyotp.TOTP(secret).now())
    assert not verify_totp(secret, "abc")
    assert not verify_totp(None, "123456")


def test_sensitive_data_filter_redacts_secrets_and_emails() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="login password=%s email=%s",
        args=("Secret123!", "ivan@example.ru"),
        exc_info=None,
    )
    SensitiveDataFilter().filter(record)
    rendered = record.getMessage()
    assert "Secret123!" not in rendered
    assert "ivan@example.ru" not in rendered
    assert "***@***" in rendered


async def test_session_store_rotation_and_revocation() -> None:
    store = InMemorySessionStore()
    await store.create(jti="j1", user_id="u1", family="f1", ttl_seconds=60)
    assert await store.get("j1") == {"user_id": "u1", "family": "f1"}
    await store.delete("j1")
    assert await store.get("j1") is None

    await store.create(jti="j2", user_id="u1", family="f1", ttl_seconds=60)
    await store.revoke_user("u1")
    assert await store.get("j2") is None


async def test_storage_presigned_ttl_and_upload_validation() -> None:
    settings = get_settings()
    storage = InMemoryObjectStorage()
    url = await storage.presigned_get_url("diplomas/x.pdf", ttl_seconds=3600)
    assert "expires_in=300" in url
    await storage.delete("diplomas/x.pdf")
    assert storage.deleted_keys == ["diplomas/x.pdf"]

    validate_diploma_upload(mime_type="application/pdf", size_bytes=1024, settings=settings)
    with pytest.raises(ValueError):
        validate_diploma_upload(mime_type="text/html", size_bytes=1024, settings=settings)
    with pytest.raises(ValueError):
        validate_diploma_upload(
            mime_type="application/pdf",
            size_bytes=settings.DIPLOMA_MAX_SIZE_BYTES + 1,
            settings=settings,
        )


def test_register_schema_rejects_weak_password_and_consent_absence() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.ru",
            password=SecretStr("short1"),
            password_confirm=SecretStr("short1"),
            role="student",
            pdn_consent=True,
        )

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.ru",
            password=SecretStr("StrongPassw0rd!2026"),
            password_confirm=SecretStr("StrongPassw0rd!2026"),
            role="student",
            pdn_consent=False,
        )

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.ru",
            password=SecretStr("StrongPassw0rd!2026"),
            password_confirm=SecretStr("OtherPassw0rd!2026"),
            role="student",
            pdn_consent=True,
        )

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.ru",
            password=SecretStr("StrongPassw0rd!2026"),
            password_confirm=SecretStr("StrongPassw0rd!2026"),
            role="admin",
            pdn_consent=True,
        )


def test_app_error_carries_machine_readable_code() -> None:
    error = AppError("csrf_failed", 403, "CSRF")
    assert (error.code, error.status_code) == ("csrf_failed", 403)


async def test_rate_limiter_blocks_after_limit() -> None:
    limiter = RateLimiter(InMemoryRateLimitBackend())
    for _ in range(3):
        assert await limiter.hit(scope="test", identity="ip", limit=3, window_seconds=60)
    assert not await limiter.hit(scope="test", identity="ip", limit=3, window_seconds=60)
