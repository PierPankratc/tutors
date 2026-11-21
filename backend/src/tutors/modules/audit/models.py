import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, event, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from tutors.core.database import Base


class AuditLog(Base):
    """Append-only журнал аудита операций с ПДн и критичных действий (152-ФЗ).

    ВАЖНО: В эту таблицу запрещено записывать значения ПДн, пароли или токены —
    только метаданные факта доступа/изменения (actor_id, action, entity, entity_id, ip).
    На уровне PostgreSQL дополнительно защищена триггером prevent_audit_log_mutation.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity_lookup", "entity", "entity_id"),
        Index("ix_audit_log_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(
            # В SQLite при unit-тестах BigInteger не автоинкрементируется без варианта INTEGER
            __import__("sqlalchemy").Integer,
            "sqlite",
        ),
        primary_key=True,
        autoincrement=True,
    )
    # Без FK ON DELETE CASCADE: удаление/обезличивание аккаунта не должно мутировать audit_log
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


@event.listens_for(AuditLog, "before_update")
def _forbid_audit_update(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("audit_log is strictly append-only: UPDATE is forbidden")


@event.listens_for(AuditLog, "before_delete")
def _forbid_audit_delete(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("audit_log is strictly append-only: DELETE is forbidden")
