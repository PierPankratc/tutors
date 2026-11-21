"""Fixed-window rate limiting for auth endpoints (defense-in-depth к Nginx)."""

import time
from typing import Protocol

from fastapi import Request
from redis.asyncio import Redis

from tutors.core.config import Settings
from tutors.core.errors import AppError
from tutors.core.net import client_ip


class RateLimitBackend(Protocol):
    async def incr(self, key: str, window_seconds: int) -> int: ...

    async def close(self) -> None: ...


class InMemoryRateLimitBackend:
    def __init__(self) -> None:
        self._counters: dict[str, tuple[int, float]] = {}

    async def incr(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        count, reset_at = self._counters.get(key, (0, now + window_seconds))
        if now >= reset_at:
            count, reset_at = 0, now + window_seconds
        count += 1
        self._counters[key] = (count, reset_at)
        return count

    async def close(self) -> None:
        self._counters.clear()


class RedisRateLimitBackend:
    def __init__(self, url: str) -> None:
        self._redis = Redis.from_url(url, decode_responses=True)

    async def incr(self, key: str, window_seconds: int) -> int:
        count = int(await self._redis.incr(key))
        if count == 1:
            await self._redis.expire(key, window_seconds)
        return count

    async def close(self) -> None:
        await self._redis.aclose()


class RateLimiter:
    def __init__(self, backend: RateLimitBackend) -> None:
        self._backend = backend

    async def hit(self, *, scope: str, identity: str, limit: int, window_seconds: int) -> bool:
        count = await self._backend.incr(f"rl:{scope}:{identity}", window_seconds)
        return count <= limit

    async def close(self) -> None:
        await self._backend.close()


def create_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.ENVIRONMENT == "testing":
        return RateLimiter(InMemoryRateLimitBackend())
    return RateLimiter(RedisRateLimitBackend(settings.REDIS_URL.get_secret_value()))


def rate_limit(scope: str, *, limit: int, window_seconds: int):  # noqa: ANN201
    async def _dependency(request: Request) -> None:
        if not getattr(request.app.state, "rate_limiting_enabled", True):
            return
        limiter: RateLimiter = request.app.state.rate_limiter
        allowed = await limiter.hit(
            scope=scope,
            identity=client_ip(request),
            limit=limit,
            window_seconds=window_seconds,
        )
        if not allowed:
            raise AppError("rate_limited", 429, "Слишком много запросов, попробуйте позже")

    return _dependency
