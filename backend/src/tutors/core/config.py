import base64
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = False

    DATABASE_URL: SecretStr
    REDIS_URL: SecretStr

    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=14, ge=1, le=30)
    CSRF_SECRET_KEY: SecretStr

    # Ключи шифрования ПДн (152-ФЗ) исключительно из переменных окружения
    PII_ENCRYPTION_KEY: SecretStr
    PII_BLIND_INDEX_KEY: SecretStr

    S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"
    S3_REGION: str = "ru-central1"
    S3_BUCKET_DIPLOMAS: str
    S3_ACCESS_KEY_ID: SecretStr
    S3_SECRET_ACCESS_KEY: SecretStr
    # Требование безопасности №4: TTL pre-signed URL строго <= 5 минут (300 с)
    S3_PRESIGNED_TTL_SECONDS: int = Field(default=300, ge=30, le=300)
    DIPLOMA_MAX_SIZE_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)

    CORS_ALLOWED_ORIGINS: list[str]
    COOKIE_SECURE: bool = True
    COOKIE_DOMAIN: str | None = None

    @field_validator("PII_ENCRYPTION_KEY")
    @classmethod
    def validate_aes256_key(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value().strip()
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        except Exception as exc:
            raise ValueError("PII_ENCRYPTION_KEY must be valid urlsafe base64") from exc
        if len(decoded) != 32:
            raise ValueError("PII_ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
        return v

    @field_validator("JWT_SECRET_KEY", "CSRF_SECRET_KEY", "PII_BLIND_INDEX_KEY")
    @classmethod
    def validate_secret_min_length(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("Cryptographic secret must be at least 32 characters long")
        return v

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: list[str]) -> list[str]:
        if not v or "*" in v:
            raise ValueError("Wildcard '*' or empty CORS_ALLOWED_ORIGINS is forbidden")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
