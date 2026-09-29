from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

password_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    tenant_id: UUID
    role: str


class InvalidAccessTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(*, user_id: UUID, tenant_id: UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_minutes)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "typ": "access",
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int((expires_at - issued_at).total_seconds())


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "tid", "role", "typ", "iat", "exp"]},
        )
        if payload["typ"] != "access":
            raise InvalidAccessTokenError("Unexpected token type")
        return AccessTokenClaims(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tid"]),
            role=str(payload["role"]),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessTokenError("Invalid access token") from exc
