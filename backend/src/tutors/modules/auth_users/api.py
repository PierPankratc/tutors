from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.core.config import Settings, get_settings
from tutors.core.database import get_db_session
from tutors.core.errors import AppError
from tutors.core.net import client_ip
from tutors.core.rate_limit import rate_limit
from tutors.core.redis import SessionStore
from tutors.core.storage import ObjectStorage
from tutors.modules.auth_users.dependencies import (
    CSRF_COOKIE_NAME,
    CurrentUser,
    require_csrf,
)
from tutors.modules.auth_users.schemas import (
    AnonymizeAccountRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    TotpConfirmRequest,
    TotpSetupResponse,
)
from tutors.modules.auth_users.services import INVALID_SESSION_MESSAGE, AuthResult, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def get_store(request: Request) -> SessionStore:
    store: SessionStore = request.app.state.session_store
    return store


def get_storage(request: Request) -> ObjectStorage:
    storage: ObjectStorage = request.app.state.storage
    return storage


def build_service(
    *,
    request: Request,
    session: AsyncSession,
    settings: Settings,
) -> AuthService:
    return AuthService(
        session,
        settings=settings,
        store=get_store(request),
        storage=get_storage(request),
    )


def _set_auth_cookies(response: Response, result: AuthResult, settings: Settings) -> None:
    max_age = result.tokens.refresh_ttl_seconds
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        result.tokens.refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        result.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth.register", limit=5, window_seconds=3600))],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegisterResponse:
    service = build_service(request=request, session=session, settings=settings)
    user = await service.register(
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        role=payload.role,
        ip=client_ip(request),
    )
    return RegisterResponse(id=user.id, message="Аккаунт создан. Теперь можно войти.")


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth.login", limit=10, window_seconds=60))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    service = build_service(request=request, session=session, settings=settings)
    result = await service.login(
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        totp_code=payload.totp_code,
        ip=client_ip(request),
    )
    _set_auth_cookies(response, result, settings)
    return TokenResponse(
        access_token=result.tokens.access_token,
        expires_in=result.tokens.access_expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit("auth.refresh", limit=30, window_seconds=60)),
    ],
)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise AppError("invalid_refresh_token", 401, INVALID_SESSION_MESSAGE)
    service = build_service(request=request, session=session, settings=settings)
    result = await service.refresh(refresh_token=refresh_token, ip=client_ip(request))
    _set_auth_cookies(response, result, settings)
    return TokenResponse(
        access_token=result.tokens.access_token,
        expires_in=result.tokens.access_expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def logout(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = build_service(request=request, session=session, settings=settings)
    await service.logout(
        refresh_token=request.cookies.get(REFRESH_COOKIE_NAME),
        ip=client_ip(request),
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response, settings)
    return response


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_totp(
    request: Request,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TotpSetupResponse:
    service = build_service(request=request, session=session, settings=settings)
    secret, provisioning_uri = await service.start_totp_setup(
        user=current_user, ip=client_ip(request)
    )
    return TotpSetupResponse(secret=secret, provisioning_uri=provisioning_uri)


@router.post("/2fa/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_totp(
    payload: TotpConfirmRequest,
    request: Request,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = build_service(request=request, session=session, settings=settings)
    await service.confirm_totp(user=current_user, code=payload.code, ip=client_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("/me", response_model=MeResponse)
async def read_me(
    request: Request,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeResponse:
    service = build_service(request=request, session=session, settings=settings)
    user = await service.read_own_profile(user=current_user, ip=client_ip(request))
    return MeResponse.model_validate(user)


@users_router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("users.anonymize", limit=5, window_seconds=3600))],
)
async def anonymize_me(
    payload: AnonymizeAccountRequest,
    request: Request,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    service = build_service(request=request, session=session, settings=settings)
    await service.anonymize_account(
        user=current_user,
        password=payload.password.get_secret_value(),
        totp_code=payload.totp_code,
        ip=client_ip(request),
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response, settings)
    return response
