from uuid import uuid4

import pytest

from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    password_hash = hash_password("ValidPassword123!")

    assert password_hash != "ValidPassword123!"
    assert verify_password("ValidPassword123!", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_contains_tenant_and_user_identity() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    token, expires_in = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="owner",
    )

    claims = decode_access_token(token)
    assert expires_in == 1800
    assert claims.user_id == user_id
    assert claims.tenant_id == tenant_id
    assert claims.role == "owner"
    assert claims.token_version == 0


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token("not-a-jwt")
