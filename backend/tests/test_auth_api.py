import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pyotp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tutors.core.crypto import get_encryptor
from tutors.core.database import get_db_session
from tutors.core.security import hash_password
from tutors.main import create_app
from tutors.modules.auth_users.models import User, UserRole
from tutors.modules.profiles.models import StudentProfile, TutorProfile, TutorProfileStatus
from tutors.modules.reviews.models import Review

PASSWORD = "StrongPassw0rd!2026"  # noqa: S105 - тестовый пароль
EMAIL = "student.ivan@example.ru"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/users/me"


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def register_payload(email: str = EMAIL, role: str = "student", password: str = PASSWORD) -> dict:
    return {
        "email": email,
        "password": password,
        "password_confirm": password,
        "role": role,
        "pdn_consent": True,
    }


async def register_and_login(
    client: AsyncClient, email: str = EMAIL, role: str = "student", password: str = PASSWORD
) -> str:
    register_response = await client.post(
        REGISTER_URL, json=register_payload(email, role, password)
    )
    assert register_response.status_code == 201, register_response.text
    login_response = await client.post(LOGIN_URL, json={"email": email, "password": password})
    assert login_response.status_code == 200, login_response.text
    return str(login_response.json()["access_token"])


def build_user(email: str, role: UserRole, password: str = PASSWORD) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        email_blind_index=get_encryptor().blind_index(email),
        password_hash=hash_password(password),
        role=role,
        pdn_consent_given_at=datetime.now(UTC),
    )


async def test_register_stores_encrypted_email_and_audit_event(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await api_client.post(REGISTER_URL, json=register_payload())
    assert response.status_code == 201, response.text

    user_id = uuid.UUID(response.json()["id"])
    blind_index = get_encryptor().blind_index(EMAIL)
    raw_email = (
        await db_session.execute(
            text("SELECT email FROM users WHERE email_blind_index = :idx"),
            {"idx": blind_index},
        )
    ).scalar_one()
    assert raw_email.startswith("v1:")
    assert EMAIL not in raw_email

    actions = (
        (
            await db_session.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :entity_id"),
                {"entity_id": str(user_id)},
            )
        )
        .scalars()
        .all()
    )
    assert "auth.register" in actions


async def test_register_rejects_weak_password_missing_consent_and_duplicates(
    api_client: AsyncClient,
) -> None:
    weak = await api_client.post(
        REGISTER_URL,
        json=register_payload(password="weakpass"),  # noqa: S106 - тест валидатора
    )
    assert weak.status_code == 422

    no_consent_payload = register_payload(email="second@example.ru") | {"pdn_consent": False}
    no_consent = await api_client.post(REGISTER_URL, json=no_consent_payload)
    assert no_consent.status_code == 422

    role_escalation = register_payload(email="third@example.ru") | {"role": "admin"}
    escalation_response = await api_client.post(REGISTER_URL, json=role_escalation)
    assert escalation_response.status_code == 422

    first = await api_client.post(REGISTER_URL, json=register_payload())
    assert first.status_code == 201
    duplicate = await api_client.post(REGISTER_URL, json=register_payload())
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "email_taken"


async def test_login_sets_httponly_refresh_and_csrf_cookies(api_client: AsyncClient) -> None:
    register_response = await api_client.post(REGISTER_URL, json=register_payload())
    assert register_response.status_code == 201

    response = await api_client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"  # noqa: S105 - тип схемы, не credential
    assert body["expires_in"] == 15 * 60
    assert body["access_token"]

    set_cookie_headers = " ".join(response.headers.get_list("set-cookie"))
    assert "refresh_token=" in set_cookie_headers
    assert "HttpOnly" in set_cookie_headers
    assert "SameSite=strict" in set_cookie_headers
    assert api_client.cookies.get("csrf_token")


async def test_login_failure_is_generic_and_audited(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await api_client.post(REGISTER_URL, json=register_payload())

    wrong_password = await api_client.post(
        LOGIN_URL, json={"email": EMAIL, "password": "WrongPassw0rd!2026"}
    )
    unknown_email = await api_client.post(
        LOGIN_URL, json={"email": "ghost@example.ru", "password": "WrongPassw0rd!2026"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["code"] == "invalid_credentials"

    failed_events = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action = 'auth.login_failed'")
        )
    ).scalar_one()
    assert failed_events == 2


async def test_me_requires_authentication_and_logs_pii_read(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    unauthorized = await api_client.get(ME_URL)
    assert unauthorized.status_code == 401

    access_token = await register_and_login(api_client)
    response = await api_client.get(ME_URL, headers=auth_headers(access_token))
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL
    assert response.json()["role"] == "student"

    pii_events = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action LIKE 'pii.read:%'")
        )
    ).scalar_one()
    assert pii_events >= 1


async def test_refresh_requires_csrf_and_rotates_tokens(api_client: AsyncClient) -> None:
    await register_and_login(api_client)

    csrf_token = api_client.cookies.get("csrf_token")
    old_refresh = api_client.cookies.get("refresh_token")
    assert csrf_token and old_refresh

    without_csrf = await api_client.post(REFRESH_URL)
    assert without_csrf.status_code == 403
    assert without_csrf.json()["code"] == "csrf_failed"

    rotated = await api_client.post(REFRESH_URL, headers={"X-CSRF-Token": csrf_token})
    assert rotated.status_code == 200
    new_refresh = api_client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh


async def test_refresh_token_reuse_revokes_all_sessions(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register_and_login(api_client)
    csrf_token = str(api_client.cookies.get("csrf_token"))
    old_refresh = str(api_client.cookies.get("refresh_token"))

    rotated = await api_client.post(REFRESH_URL, headers={"X-CSRF-Token": csrf_token})
    assert rotated.status_code == 200

    api_client.cookies.clear()
    reuse = await api_client.post(
        REFRESH_URL,
        headers={
            "X-CSRF-Token": csrf_token,
            "Cookie": f"refresh_token={old_refresh}; csrf_token={csrf_token}",
        },
    )
    assert reuse.status_code == 401
    assert reuse.json()["code"] == "invalid_refresh_token"

    reuse_events = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action = 'auth.refresh_reuse_detected'")
        )
    ).scalar_one()
    assert reuse_events == 1


async def test_logout_revokes_session_and_clears_cookies(api_client: AsyncClient) -> None:
    await register_and_login(api_client)
    csrf_token = str(api_client.cookies.get("csrf_token"))

    logout = await api_client.post(LOGOUT_URL, headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 204
    assert api_client.cookies.get("refresh_token") is None

    refresh = await api_client.post(REFRESH_URL, headers={"X-CSRF-Token": csrf_token})
    assert refresh.status_code == 403  # CSRF-cookie удалён вместе с сессией

    api_client.cookies.clear()
    refresh_without_session = await api_client.post(
        REFRESH_URL,
        headers={"X-CSRF-Token": csrf_token, "Cookie": f"csrf_token={csrf_token}"},
    )
    assert refresh_without_session.status_code == 401


async def test_totp_setup_confirm_and_login_flow(api_client: AsyncClient) -> None:
    access_token = await register_and_login(api_client)

    setup = await api_client.post("/api/v1/auth/2fa/setup", headers=auth_headers(access_token))
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert "otpauth://totp/" in setup.json()["provisioning_uri"]

    invalid = await api_client.post(
        "/api/v1/auth/2fa/confirm",
        json={"code": "000000"},
        headers=auth_headers(access_token),
    )
    assert invalid.status_code == 400

    confirm = await api_client.post(
        "/api/v1/auth/2fa/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers=auth_headers(access_token),
    )
    assert confirm.status_code == 204

    without_code = await api_client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert without_code.status_code == 401
    assert without_code.json()["code"] == "totp_required"

    with_code = await api_client.post(
        LOGIN_URL,
        json={"email": EMAIL, "password": PASSWORD, "totp_code": pyotp.TOTP(secret).now()},
    )
    assert with_code.status_code == 200


async def test_delete_account_anonymizes_all_pii(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    access_token = await register_and_login(api_client)
    me = await api_client.get(ME_URL, headers=auth_headers(access_token))
    student_id = uuid.UUID(me.json()["id"])

    tutor = build_user("tutor.petr@example.ru", UserRole.TUTOR)
    db_session.add(tutor)
    await db_session.flush()
    db_session.add(
        StudentProfile(user_id=student_id, display_name="Иван", grade=9, contact="+79990001122")
    )
    db_session.add(
        TutorProfile(
            user_id=tutor.id,
            display_name="Пётр",
            bio="Репетитор по математике",
            price=Decimal("1500.00"),
            experience=5,
            status=TutorProfileStatus.PUBLISHED,
        )
    )
    await db_session.flush()
    db_session.add(
        Review(student_id=student_id, tutor_id=tutor.id, rating=5, text="Иван, отличный репетитор")
    )
    await db_session.commit()

    response = await api_client.request(
        "DELETE",
        ME_URL,
        headers=auth_headers(access_token),
        json={"password": PASSWORD},
    )
    assert response.status_code == 204

    user = await db_session.get(User, student_id)
    assert user is not None
    assert user.is_active is False
    assert user.anonymized_at is not None
    assert user.email.endswith("@anonymized.invalid")

    # Проверяем шифрование at-rest: в SQLite UUID хранится без дефисов
    raw_email = (
        await db_session.execute(
            text("SELECT email FROM users WHERE id = :id"),
            {"id": student_id.hex},
        )
    ).scalar_one()
    assert raw_email.startswith("v1:")
    assert get_encryptor().decrypt(raw_email).endswith("@anonymized.invalid")

    profiles_left = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM student_profiles WHERE user_id = :id"),
            {"id": student_id.hex},
        )
    ).scalar_one()
    assert profiles_left == 0

    review_row = (
        await db_session.execute(
            text("SELECT student_id, text FROM reviews WHERE tutor_id = :id"),
            {"id": tutor.id.hex},
        )
    ).one()
    assert review_row[0] is None
    assert review_row[1] == ""

    anonymized_events = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action = 'account.anonymized'")
        )
    ).scalar_one()
    assert anonymized_events == 1

    relogin = await api_client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert relogin.status_code == 401


async def test_audit_endpoint_requires_moderator_role(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    student_token = await register_and_login(api_client)
    forbidden = await api_client.get("/api/v1/audit/events", headers=auth_headers(student_token))
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "forbidden"

    db_session.add(build_user("admin@example.ru", UserRole.ADMIN))
    await db_session.commit()

    admin_login = await api_client.post(
        LOGIN_URL, json={"email": "admin@example.ru", "password": PASSWORD}
    )
    assert admin_login.status_code == 200
    allowed = await api_client.get(
        "/api/v1/audit/events",
        headers=auth_headers(str(admin_login.json()["access_token"])),
    )
    assert allowed.status_code == 200
    assert isinstance(allowed.json()["items"], list)


async def test_login_is_rate_limited(db_session: AsyncSession) -> None:
    app = create_app(enable_rate_limiting=True)

    async def _override_db():  # noqa: ANN202
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = [
            await client.post(
                LOGIN_URL, json={"email": "ghost@example.ru", "password": "WrongPassw0rd!2026"}
            )
            for _ in range(11)
        ]

    assert responses[0].status_code == 401
    assert responses[-1].status_code == 429
    assert responses[-1].json()["code"] == "rate_limited"
