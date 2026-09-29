import re
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=2, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def normalize_login_values(cls, value: str) -> str:
        return value.strip().lower()


class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=200)
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("tenant_name")
    @classmethod
    def normalize_tenant_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("username", "email")
    @classmethod
    def normalize_registration_identity(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def validate_registration_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid address")
        return value


class TenantSummary(BaseModel):
    id: UUID
    name: str
    slug: str


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    username: str
    email: str
    role: UserRole
    is_platform_admin: bool
    status: str
    last_login_at: datetime | None
    created_at: datetime


class SessionResponse(BaseModel):
    user: UserSummary
    tenant: TenantSummary


class TokenResponse(SessionResponse):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.MEMBER

    @field_validator("username", "email")
    @classmethod
    def normalize_identity(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid address")
        return value


class UserListResponse(BaseModel):
    items: list[UserSummary]
