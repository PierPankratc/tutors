import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.modules.audit.models import AuditLog


class AuditLogRepository:
    """Единственный слой, который пишет в audit_log. Только append-only операции."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(
        self,
        *,
        action: str,
        entity: str,
        entity_id: str,
        actor_id: uuid.UUID | None,
        ip: str,
    ) -> None:
        self._session.add(
            AuditLog(
                actor_id=actor_id,
                action=action[:128],
                entity=entity[:64],
                entity_id=entity_id[:64],
                ip=ip,
            )
        )

    async def list_events(self, *, limit: int, offset: int) -> Sequence[AuditLog]:
        result = await self._session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
