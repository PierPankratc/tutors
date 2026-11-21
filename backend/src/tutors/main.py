from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tutors.api.v1 import api_router
from tutors.core.config import get_settings
from tutors.core.errors import AppError
from tutors.core.logging import configure_logging
from tutors.core.rate_limit import create_rate_limiter
from tutors.core.redis import create_session_store
from tutors.core.storage import create_storage


def create_app(*, enable_rate_limiting: bool | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await app.state.session_store.close()
        await app.state.rate_limiter.close()

    app = FastAPI(
        title="Tutors Marketplace API",
        version="0.1.0",
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.session_store = create_session_store(settings)
    app.state.storage = create_storage(settings)
    app.state.rate_limiter = create_rate_limiter(settings)
    app.state.rate_limiting_enabled = (
        settings.ENVIRONMENT != "testing" if enable_rate_limiting is None else enable_rate_limiting
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # noqa: ANN001, ANN202
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    app.include_router(api_router)
    return app


app = create_app()
