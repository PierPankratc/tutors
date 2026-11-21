import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.core.config import Settings, get_settings
from tutors.core.database import get_db_session
from tutors.core.errors import AppError
from tutors.core.security import (
    InvalidTokenError,
    csrf_tokens_match,
    decode_token,
    verify_csrf_token,
)
from tutors.modules.auth_users.models import User, UserRole
from tutors.modules.auth_users.repositories import UserRepository

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("unauthorized", 401, "Требуется аутентификация")
    try:
        claims = decode_token(settings, credentials.credentials, expected_type="access")
        user_id = uuid.UUID(str(claims["sub"]))
    except InvalidTokenError, ValueError:
        raise AppError("invalid_token", 401, "Требуется аутентификация") from None

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active or user.anonymized_at is not None:
        raise AppError("unauthorized", 401, "Требуется аутентификация")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: UserRole):  # noqa: ANN201 - FastAPI dependency factory
    async def _dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError("forbidden", 403, "Недостаточно прав")
        return user

    return _dependency


async def require_csrf(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Double-submit CSRF: подписанный cookie обязан совпасть с заголовком X-CSRF-Token."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if (
        not cookie_token
        or not verify_csrf_token(settings, cookie_token)
        or not csrf_tokens_match(cookie_token, header_token)
    ):
        raise AppError("csrf_failed", 403, "CSRF-токен отсутствует или недействителен")
