import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.modules.verification.models import VerificationDocument


class VerificationDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_s3_keys(self, tutor_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(VerificationDocument.s3_key).where(VerificationDocument.tutor_id == tutor_id)
        )
        return list(result.scalars().all())
