"""API layer composition (v1)."""

from fastapi import APIRouter

from tutors.modules.audit.api import router as audit_router
from tutors.modules.auth_users.api import router as auth_router
from tutors.modules.auth_users.api import users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(audit_router)

__all__ = ["api_router"]
