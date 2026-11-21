import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from tutors.modules.audit.models import AuditLog
from tutors.modules.audit.repositories import AuditLogRepository


class AuditService:
    """Фиксирует факты доступа к ПДн и критичные действия.

    В журнал никогда не попадают значения ПДн, пароли или токены — только
    идентификаторы сущностей и имена затронутых полей.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repository = AuditLogRepository(session)

    def record(
        self,
        *,
        action: str,
        entity: str,
        entity_id: str,
        actor_id: uuid.UUID | None,
        ip: str,
    ) -> None:
        self._repository.add(
            action=action,
            entity=entity,
            entity_id=entity_id,
            actor_id=actor_id,
            ip=ip,
        )

    def pii_read(
        self,
        *,
        actor_id: uuid.UUID | None,
        entity: str,
        entity_id: str,
        fields: tuple[str, ...],
        ip: str,
    ) -> None:
        self.record(
            action=f"pii.read:{','.join(fields)}",
            entity=entity,
            entity_id=entity_id,
            actor_id=actor_id,
            ip=ip,
        )

    def pii_update(
        self,
        *,
        actor_id: uuid.UUID | None,
        entity: str,
        entity_id: str,
        fields: tuple[str, ...],
        ip: str,
    ) -> None:
        self.record(
            action=f"pii.update:{','.join(fields)}",
            entity=entity,
            entity_id=entity_id,
            actor_id=actor_id,
            ip=ip,
        )

    async def list_events(self, *, limit: int, offset: int) -> Sequence[AuditLog]:
        return await self._repository.list_events(limit=limit, offset=offset)
