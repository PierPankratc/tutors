import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tutors.core.config import Settings
from tutors.core.crypto import get_encryptor
from tutors.core.errors import AppError
from tutors.core.redis import SessionStore
from tutors.core.security import (
    InvalidTokenError,
    TokenPair,
    create_access_token,
    create_refresh_token,
    decode_token,
    dummy_verify,
    generate_csrf_token,
    generate_totp_secret,
    hash_password,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from tutors.core.storage import ObjectStorage
from tutors.modules.audit.services import AuditService
from tutors.modules.auth_users.models import User, UserRole
from tutors.modules.auth_users.repositories import UserRepository
from tutors.modules.profiles.repositories import StudentProfileRepository, TutorProfileRepository
from tutors.modules.reviews.repositories import ReviewRepository
from tutors.modules.verification.repositories import VerificationDocumentRepository

INVALID_CREDENTIALS_MESSAGE = "Неверный email или пароль"
INVALID_SESSION_MESSAGE = "Сессия истекла, войдите заново"


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    tokens: TokenPair
    csrf_token: str


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings,
        store: SessionStore,
        storage: ObjectStorage,
    ) -> None:
        self._session = session
        self._settings = settings
        self._store = store
        self._storage = storage
        self.users = UserRepository(session)
        self.audit = AuditService(session)
        self.student_profiles = StudentProfileRepository(session)
        self.tutor_profiles = TutorProfileRepository(session)
        self.reviews = ReviewRepository(session)
        self.verification = VerificationDocumentRepository(session)

    async def register(self, *, email: str, password: str, role: str, ip: str) -> User:
        normalized_email = email.strip().lower()
        if await self.users.get_by_email(normalized_email) is not None:
            raise AppError("email_taken", 409, "Пользователь с таким email уже существует")
        try:
            user = await self.users.create(
                email=normalized_email,
                password_hash=hash_password(password),
                role=UserRole(role),
                pdn_consent_given_at=datetime.now(UTC),
            )
            self.audit.record(
                action="auth.register",
                entity="users",
                entity_id=str(user.id),
                actor_id=user.id,
                ip=ip,
            )
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise AppError(
                "email_taken", 409, "Пользователь с таким email уже существует"
            ) from None
        return user

    async def login(
        self, *, email: str, password: str, totp_code: str | None, ip: str
    ) -> AuthResult:
        normalized_email = email.strip().lower()
        user = await self.users.get_by_email(normalized_email)

        if user is None or user.anonymized_at is not None:
            dummy_verify(password)
            await self._record_login_failure(normalized_email, action="auth.login_failed", ip=ip)
            raise AppError("invalid_credentials", 401, INVALID_CREDENTIALS_MESSAGE)

        is_valid, needs_rehash = verify_password(user.password_hash, password)
        if not is_valid:
            await self._record_login_failure(normalized_email, action="auth.login_failed", ip=ip)
            raise AppError("invalid_credentials", 401, INVALID_CREDENTIALS_MESSAGE)

        if not user.is_active:
            self.audit.record(
                action="auth.login_blocked_inactive",
                entity="users",
                entity_id=str(user.id),
                actor_id=None,
                ip=ip,
            )
            await self._session.commit()
            raise AppError("account_disabled", 403, "Аккаунт отключён")

        if user.is_totp_enabled:
            if not totp_code:
                self.audit.record(
                    action="auth.totp_required",
                    entity="users",
                    entity_id=str(user.id),
                    actor_id=None,
                    ip=ip,
                )
                await self._session.commit()
                raise AppError("totp_required", 401, "Требуется код двухфакторной аутентификации")
            if not verify_totp(user.totp_secret, totp_code):
                await self._record_login_failure(normalized_email, action="auth.totp_failed", ip=ip)
                raise AppError("invalid_credentials", 401, INVALID_CREDENTIALS_MESSAGE)

        if needs_rehash:
            user.password_hash = hash_password(password)

        tokens = await self._issue_tokens(user)
        self.audit.record(
            action="auth.login",
            entity="users",
            entity_id=str(user.id),
            actor_id=user.id,
            ip=ip,
        )
        await self._session.commit()
        return AuthResult(user=user, tokens=tokens, csrf_token=generate_csrf_token(self._settings))

    async def _record_login_failure(self, email: str, *, action: str, ip: str) -> None:
        # В audit_log пишем только HMAC-индекс email, никогда сам адрес
        blind_index = get_encryptor().blind_index(email)
        self.audit.record(
            action=action,
            entity="users",
            entity_id=blind_index,
            actor_id=None,
            ip=ip,
        )
        await self._session.commit()

    async def _issue_tokens(self, user: User, *, family: str | None = None) -> TokenPair:
        access_token, expires_in = create_access_token(
            self._settings, user_id=user.id, role=user.role.value
        )
        refresh_token, jti, token_family, ttl = create_refresh_token(
            self._settings,
            user_id=user.id,
            role=user.role.value,
            family=family,
        )
        await self._store.create(
            jti=jti, user_id=str(user.id), family=token_family, ttl_seconds=ttl
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=expires_in,
            refresh_ttl_seconds=ttl,
            refresh_jti=jti,
            refresh_family=token_family,
        )

    async def refresh(self, *, refresh_token: str, ip: str) -> AuthResult:
        try:
            claims = decode_token(self._settings, refresh_token, expected_type="refresh")
            user_id = uuid.UUID(str(claims["sub"]))
            jti = str(claims["jti"])
            family = str(claims["family"])
        except InvalidTokenError, KeyError, ValueError:
            raise AppError("invalid_refresh_token", 401, INVALID_SESSION_MESSAGE) from None

        record = await self._store.get(jti)
        if record is None or record.get("user_id") != str(user_id):
            # Повторное использование ротированного токена — компрометация: рвём все сессии
            await self._store.revoke_user(str(user_id))
            self.audit.record(
                action="auth.refresh_reuse_detected",
                entity="users",
                entity_id=str(user_id),
                actor_id=user_id,
                ip=ip,
            )
            await self._session.commit()
            raise AppError("invalid_refresh_token", 401, INVALID_SESSION_MESSAGE)

        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active or user.anonymized_at is not None:
            await self._store.delete(jti)
            raise AppError("invalid_refresh_token", 401, INVALID_SESSION_MESSAGE)

        await self._store.delete(jti)
        tokens = await self._issue_tokens(user, family=family)
        self.audit.record(
            action="auth.refresh",
            entity="users",
            entity_id=str(user.id),
            actor_id=user.id,
            ip=ip,
        )
        await self._session.commit()
        return AuthResult(user=user, tokens=tokens, csrf_token=generate_csrf_token(self._settings))

    async def logout(self, *, refresh_token: str | None, ip: str) -> None:
        if not refresh_token:
            return
        try:
            claims = decode_token(self._settings, refresh_token, expected_type="refresh")
            jti = str(claims["jti"])
            user_id = uuid.UUID(str(claims["sub"]))
        except InvalidTokenError, KeyError, ValueError:
            return
        await self._store.delete(jti)
        self.audit.record(
            action="auth.logout",
            entity="users",
            entity_id=str(user_id),
            actor_id=user_id,
            ip=ip,
        )
        await self._session.commit()

    async def read_own_profile(self, *, user: User, ip: str) -> User:
        self.audit.pii_read(
            actor_id=user.id,
            entity="users",
            entity_id=str(user.id),
            fields=("email", "role", "is_totp_enabled"),
            ip=ip,
        )
        await self._session.commit()
        return user

    async def start_totp_setup(self, *, user: User, ip: str) -> tuple[str, str]:
        secret = generate_totp_secret()
        user.totp_secret = secret
        user.is_totp_enabled = False
        self.audit.record(
            action="auth.totp_setup",
            entity="users",
            entity_id=str(user.id),
            actor_id=user.id,
            ip=ip,
        )
        await self._session.commit()
        return secret, totp_provisioning_uri(secret, user.email)

    async def confirm_totp(self, *, user: User, code: str, ip: str) -> None:
        if not user.totp_secret:
            raise AppError("totp_not_started", 400, "Сначала запросите настройку 2FA")
        if not verify_totp(user.totp_secret, code):
            self.audit.record(
                action="auth.totp_confirm_failed",
                entity="users",
                entity_id=str(user.id),
                actor_id=user.id,
                ip=ip,
            )
            await self._session.commit()
            raise AppError("totp_invalid", 400, "Неверный код подтверждения")
        user.is_totp_enabled = True
        self.audit.record(
            action="auth.totp_enabled",
            entity="users",
            entity_id=str(user.id),
            actor_id=user.id,
            ip=ip,
        )
        await self._session.commit()

    async def anonymize_account(
        self, *, user: User, password: str, totp_code: str | None, ip: str
    ) -> None:
        is_valid, _ = verify_password(user.password_hash, password)
        if not is_valid:
            self.audit.record(
                action="account.anonymize_failed",
                entity="users",
                entity_id=str(user.id),
                actor_id=user.id,
                ip=ip,
            )
            await self._session.commit()
            raise AppError("invalid_credentials", 401, INVALID_CREDENTIALS_MESSAGE)

        if user.is_totp_enabled and not verify_totp(user.totp_secret, totp_code):
            raise AppError("totp_invalid", 400, "Неверный код подтверждения")

        anonymized_email = f"deleted-{uuid.uuid4().hex}@anonymized.invalid"
        user.email = anonymized_email
        user.email_blind_index = get_encryptor().blind_index(anonymized_email)
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.totp_secret = None
        user.is_totp_enabled = False
        user.is_active = False
        user.anonymized_at = datetime.now(UTC)

        await self._store.revoke_user(str(user.id))
        for s3_key in await self.verification.list_s3_keys(user.id):
            await self._storage.delete(s3_key)
        await self.reviews.anonymize_authored(user.id)
        await self.student_profiles.delete_for_user(user.id)
        await self.tutor_profiles.delete_for_user(user.id)

        self.audit.record(
            action="account.anonymized",
            entity="users",
            entity_id=str(user.id),
            actor_id=user.id,
            ip=ip,
        )
        await self._session.commit()
