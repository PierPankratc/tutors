import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.core.crypto import get_encryptor
from tutors.modules.auth_users.models import User, UserRole


class UserRepository:
    """Единственное место SQL-доступа к users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        blind_index = get_encryptor().blind_index(email)
        result = await self._session.execute(
            select(User).where(User.email_blind_index == blind_index)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole,
        pdn_consent_given_at: datetime,
    ) -> User:
        blind_index = get_encryptor().blind_index(email)
        user = User(
            email=email,
            email_blind_index=blind_index,
            password_hash=password_hash,
            role=role,
            pdn_consent_given_at=pdn_consent_given_at,
        )
        self._session.add(user)
        await self._session.flush()
        return user
