import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.modules.profiles.models import StudentProfile, TutorProfile


class StudentProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> StudentProfile | None:
        return await self._session.get(StudentProfile, user_id)

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(delete(StudentProfile).where(StudentProfile.user_id == user_id))


class TutorProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> TutorProfile | None:
        return await self._session.get(TutorProfile, user_id)

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        await self._session.execute(delete(TutorProfile).where(TutorProfile.user_id == user_id))
