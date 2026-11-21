import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from tutors.modules.auth_users.models import UserRole

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def _validate_password_strength(password: SecretStr) -> SecretStr:
    value = password.get_secret_value()
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Пароль должен содержать минимум {PASSWORD_MIN_LENGTH} символов")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Пароль не должен превышать {PASSWORD_MAX_LENGTH} символов")
    if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("Пароль должен содержать буквы и цифры")
    return password


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    password: SecretStr
    password_confirm: SecretStr
    role: Literal["student", "tutor"]
    pdn_consent: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        return _validate_password_strength(value)

    @field_validator("pdn_consent")
    @classmethod
    def validate_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Требуется согласие на обработку персональных данных (152-ФЗ)")
        return value

    @model_validator(mode="after")
    def validate_passwords_match(self) -> RegisterRequest:
        if self.password.get_secret_value() != self.password_confirm.get_secret_value():
            raise ValueError("Пароли не совпадают")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    password: SecretStr
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - не credential
    expires_in: int


class RegisterResponse(BaseModel):
    id: uuid.UUID
    message: str


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    is_totp_enabled: bool
    pdn_consent_given_at: datetime
    created_at: datetime


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^\d{6}$")


class AnonymizeAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: SecretStr
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")
