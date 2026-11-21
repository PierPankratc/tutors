"""Private S3-compatible storage (Yandex Object Storage): pre-signed URLs only."""

from typing import Protocol

from aiobotocore.session import get_session

from tutors.core.config import Settings

DIPLOMA_MIME_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png"})
MAX_PRESIGNED_TTL_SECONDS = 300


class ObjectStorage(Protocol):
    async def presigned_get_url(self, key: str, *, ttl_seconds: int | None = None) -> str: ...

    async def delete(self, key: str) -> None: ...


def validate_diploma_upload(*, mime_type: str, size_bytes: int, settings: Settings) -> None:
    """MIME и размер проверяются до выдачи pre-signed URL на загрузку."""
    if mime_type not in DIPLOMA_MIME_TYPES:
        raise ValueError("unsupported diploma mime type")
    if size_bytes <= 0 or size_bytes > settings.DIPLOMA_MAX_SIZE_BYTES:
        raise ValueError("diploma size is out of allowed bounds")


class YandexObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _client(self) -> object:
        session = get_session()
        return session.create_client(
            "s3",
            endpoint_url=self._settings.S3_ENDPOINT_URL,
            region_name=self._settings.S3_REGION,
            aws_access_key_id=self._settings.S3_ACCESS_KEY_ID.get_secret_value(),
            aws_secret_access_key=self._settings.S3_SECRET_ACCESS_KEY.get_secret_value(),
        )

    def _ttl(self, ttl_seconds: int | None) -> int:
        requested = ttl_seconds or self._settings.S3_PRESIGNED_TTL_SECONDS
        # Жёсткий потолок 300 с: даже при ошибке конфигурации ссылка живёт не дольше 5 минут
        return max(
            1, min(requested, self._settings.S3_PRESIGNED_TTL_SECONDS, MAX_PRESIGNED_TTL_SECONDS)
        )

    async def presigned_get_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        async with await self._client() as client:  # type: ignore[attr-defined]
            url: str = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._settings.S3_BUCKET_DIPLOMAS, "Key": key},
                ExpiresIn=self._ttl(ttl_seconds),
            )
            return url

    async def delete(self, key: str) -> None:
        async with await self._client() as client:  # type: ignore[attr-defined]
            await client.delete_object(Bucket=self._settings.S3_BUCKET_DIPLOMAS, Key=key)


class InMemoryObjectStorage:
    """Тестовый адаптер: фиксирует удаления и выдаёт ссылки с ограниченным TTL."""

    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    async def presigned_get_url(self, key: str, *, ttl_seconds: int | None = None) -> str:
        ttl = max(1, min(ttl_seconds or MAX_PRESIGNED_TTL_SECONDS, MAX_PRESIGNED_TTL_SECONDS))
        return f"https://storage.invalid/{key}?expires_in={ttl}"

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


def create_storage(settings: Settings) -> ObjectStorage:
    if settings.ENVIRONMENT == "testing":
        return InMemoryObjectStorage()
    return YandexObjectStorage(settings)
