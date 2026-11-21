"""Refresh-token session storage with rotation and reuse detection."""

import asyncio
import json
import time
from typing import Protocol

from redis.asyncio import Redis

from tutors.core.config import Settings

_KEY_PREFIX = "auth:refresh:"
_USER_PREFIX = "auth:user_sessions:"


class SessionStore(Protocol):
    async def create(self, *, jti: str, user_id: str, family: str, ttl_seconds: int) -> None: ...

    async def get(self, jti: str) -> dict[str, str] | None: ...

    async def delete(self, jti: str) -> None: ...

    async def revoke_user(self, user_id: str) -> None: ...

    async def close(self) -> None: ...


class RedisSessionStore:
    """Сессии храним только в Redis: ПДн там нет, только id пользователя и id семьи токенов."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._redis: Redis | None = None

    def _client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self._url, decode_responses=True)
        return self._redis

    async def create(self, *, jti: str, user_id: str, family: str, ttl_seconds: int) -> None:
        client = self._client()
        async with client.pipeline(transaction=True) as pipe:
            pipe.set(
                f"{_KEY_PREFIX}{jti}",
                json.dumps({"user_id": user_id, "family": family}),
                ex=ttl_seconds,
            )
            pipe.sadd(f"{_USER_PREFIX}{user_id}", jti)
            pipe.expire(f"{_USER_PREFIX}{user_id}", ttl_seconds)
            await pipe.execute()

    async def get(self, jti: str) -> dict[str, str] | None:
        raw = await self._client().get(f"{_KEY_PREFIX}{jti}")
        if raw is None:
            return None
        data: dict[str, str] = json.loads(raw)
        return data

    async def delete(self, jti: str) -> None:
        client = self._client()
        raw = await client.get(f"{_KEY_PREFIX}{jti}")
        if raw is not None:
            user_id = json.loads(raw).get("user_id")
            if user_id:
                await client.srem(f"{_USER_PREFIX}{user_id}", jti)
        await client.delete(f"{_KEY_PREFIX}{jti}")

    async def revoke_user(self, user_id: str) -> None:
        client = self._client()
        key = f"{_USER_PREFIX}{user_id}"
        members = await client.smembers(key)
        if members:
            await client.delete(*[f"{_KEY_PREFIX}{jti}" for jti in members])
        await client.delete(key)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


class InMemorySessionStore:
    """Тестовый/локальный адаптер с теми же гарантиями, без внешнего Redis."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, str]] = {}
        self._expiry: dict[str, float] = {}
        self._user_sessions: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    def _purge_if_expired(self, jti: str) -> None:
        expires_at = self._expiry.get(jti)
        if expires_at is not None and expires_at <= time.monotonic():
            self._sessions.pop(jti, None)
            self._expiry.pop(jti, None)

    async def create(self, *, jti: str, user_id: str, family: str, ttl_seconds: int) -> None:
        async with self._lock:
            self._sessions[jti] = {"user_id": user_id, "family": family}
            self._expiry[jti] = time.monotonic() + ttl_seconds
            self._user_sessions.setdefault(user_id, set()).add(jti)

    async def get(self, jti: str) -> dict[str, str] | None:
        async with self._lock:
            self._purge_if_expired(jti)
            return self._sessions.get(jti)

    async def delete(self, jti: str) -> None:
        async with self._lock:
            record = self._sessions.pop(jti, None)
            self._expiry.pop(jti, None)
            if record is not None:
                self._user_sessions.get(record["user_id"], set()).discard(jti)

    async def revoke_user(self, user_id: str) -> None:
        async with self._lock:
            for jti in self._user_sessions.pop(user_id, set()):
                self._sessions.pop(jti, None)
                self._expiry.pop(jti, None)

    async def close(self) -> None:
        async with self._lock:
            self._sessions.clear()
            self._expiry.clear()
            self._user_sessions.clear()


def create_session_store(settings: Settings) -> SessionStore:
    if settings.ENVIRONMENT == "testing":
        return InMemorySessionStore()
    return RedisSessionStore(settings.REDIS_URL.get_secret_value())
