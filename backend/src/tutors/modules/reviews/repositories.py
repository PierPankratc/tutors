import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.modules.reviews.models import Review


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def anonymize_authored(self, student_id: uuid.UUID) -> None:
        """Обезличивает автора отзыва, сохраняя агрегированный рейтинг репетитора."""
        await self._session.execute(
            update(Review).where(Review.student_id == student_id).values(student_id=None, text="")
        )
