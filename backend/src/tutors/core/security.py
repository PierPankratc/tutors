"""Argon2id passwords, JWT access/refresh tokens, CSRF double-submit, TOTP 2FA."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from tutors.core.config import Settings

JWT_ISSUER = "tutors-api"
JWT_AUDIENCE = "tutors-web"

# Параметры Argon2id: 64 MiB, 3 итерации, 4 потока (OWASP minimum)
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


class InvalidTokenError(Exception):
    """Raised when JWT is malformed, expired or has an unexpected type."""


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_ttl_seconds: int
    refresh_jti: str
    refresh_family: str


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> tuple[bool, bool]:
    """Returns (is_valid, needs_rehash). Никогда не логирует входные значения."""
    try:
        _hasher.verify(password_hash, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False, False
    return True, _hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(32))


def dummy_verify(password: str) -> None:
    """Выравнивает время ответа для несуществующих email (анти-энумерация)."""
    verify_password(_dummy_hash(), password)


def _encode(settings: Settings, payload: dict[str, object]) -> str:
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(settings: Settings, *, user_id: uuid.UUID, role: str) -> tuple[str, int]:
    now = datetime.now(UTC)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    token = _encode(
        settings,
        {
            "sub": str(user_id),
            "role": role,
            "type": "access",
            "jti": uuid.uuid4().hex,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        },
    )
    return token, expires_in


def create_refresh_token(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    role: str,
    family: str | None = None,
) -> tuple[str, str, str, int]:
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    token_family = family or uuid.uuid4().hex
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    token = _encode(
        settings,
        {
            "sub": str(user_id),
            "role": role,
            "type": "refresh",
            "jti": jti,
            "family": token_family,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        },
    )
    return token, jti, token_family, ttl


def decode_token(settings: Settings, token: str, *, expected_type: str) -> dict[str, object]:
    try:
        claims: dict[str, object] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti", "type"]},
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("invalid token") from exc
    if claims.get("type") != expected_type:
        raise InvalidTokenError("unexpected token type")
    return claims


def generate_csrf_token(settings: Settings) -> str:
    nonce = secrets.token_urlsafe(32)
    digest = hmac.new(
        settings.CSRF_SECRET_KEY.get_secret_value().encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{nonce}.{digest}"


def verify_csrf_token(settings: Settings, token: str) -> bool:
    try:
        nonce, digest = token.split(".", 1)
    except ValueError:
        return False
    expected = hmac.new(
        settings.CSRF_SECRET_KEY.get_secret_value().encode("utf-8"),
        nonce.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, expected)


def csrf_tokens_match(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name="Tutors")


def verify_totp(secret: str | None, code: str | None) -> bool:
    if not secret or not code or len(code) != 6 or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
