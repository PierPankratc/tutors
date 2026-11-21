from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.core.database import get_db_session
from tutors.core.net import client_ip
from tutors.modules.audit.schemas import AuditEventListResponse, AuditEventResponse
from tutors.modules.audit.services import AuditService
from tutors.modules.auth_users.dependencies import require_roles
from tutors.modules.auth_users.models import User, UserRole

router = APIRouter(prefix="/audit", tags=["audit"])

ModeratorUser = Annotated[User, Depends(require_roles(UserRole.MODERATOR, UserRole.ADMIN))]


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    request: Request,
    current_user: ModeratorUser,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> AuditEventListResponse:
    service = AuditService(session)
    events = await service.list_events(limit=limit, offset=offset)
    service.record(
        action="audit.read",
        entity="audit_log",
        entity_id=str(current_user.id),
        actor_id=current_user.id,
        ip=client_ip(request),
    )
    await session.commit()
    return AuditEventListResponse(
        items=[AuditEventResponse.model_validate(event) for event in events],
        total_returned=len(events),
    )
