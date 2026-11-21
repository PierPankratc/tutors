import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator

from tutors.core.config import get_settings

_NONCE_SIZE = 12
_VERSION_PREFIX = "v1:"


class FieldEncryptor:
    """Аутентифицированное шифрование ПДн (AES-256-GCM) на уровне приложения (152-ФЗ)."""

    def __init__(self, key_b64: str, blind_index_key: str) -> None:
        key_bytes = base64.urlsafe_b64decode(key_b64.encode("ascii"))
        if len(key_bytes) != 32:
            raise ValueError("AES-256-GCM requires a 32-byte key")
        self._aesgcm = AESGCM(key_bytes)
        self._blind_key = blind_index_key.encode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(_NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{_VERSION_PREFIX}{payload}"

    def decrypt(self, token: str) -> str:
        if not token.startswith(_VERSION_PREFIX):
            raise ValueError("Unsupported encrypted payload version")
        raw = base64.urlsafe_b64decode(token[len(_VERSION_PREFIX) :].encode("ascii"))
        if len(raw) <= _NONCE_SIZE + 16:
            raise ValueError("Malformed encrypted payload")
        nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def blind_index(self, value: str) -> str:
        """Детерминированный HMAC-SHA256 для поиска по email без открытых ПДн в индексе."""
        normalized = value.strip().lower().encode("utf-8")
        return hmac.new(self._blind_key, normalized, hashlib.sha256).hexdigest()


def get_encryptor() -> FieldEncryptor:
    settings = get_settings()
    return FieldEncryptor(
        key_b64=settings.PII_ENCRYPTION_KEY.get_secret_value(),
        blind_index_key=settings.PII_BLIND_INDEX_KEY.get_secret_value(),
    )


class EncryptedString(TypeDecorator[str]):
    """Прозрачное шифрование чувствительных ПДн-колонок при записи в БД."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return get_encryptor().encrypt(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return get_encryptor().decrypt(value)


class BlindIndexString(String):
    """64-символьный hex HMAC-SHA256 индекс."""

    def __init__(self) -> None:
        super().__init__(length=64)
