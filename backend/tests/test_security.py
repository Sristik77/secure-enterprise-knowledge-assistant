
from datetime import timedelta
import uuid

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verified():
    password = "Test-Password-123!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("Wrong-Password!", hashed)


def test_password_hashes_are_salted():
    password = "Test-Password-123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert verify_password(password, second_hash)


def test_access_token_contains_user_id():
    user_id = uuid.uuid4()

    token = create_access_token(user_id)
    claims = decode_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["type"] == "access"
    assert "iat" in claims
    assert "exp" in claims


def test_expired_token_is_rejected():
    token = create_access_token(
        uuid.uuid4(),
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_signed_with_wrong_secret_is_rejected():
    settings = get_settings()
    user_id = uuid.uuid4()

    token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": 1_800_000_000,
            "exp": 4_000_000_000,
            "type": "access",
        },
        "not-the-application-secret",
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_non_access_token_is_rejected():
    user_id = uuid.uuid4()

    token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": 1_800_000_000,
            "exp": 4_000_000_000,
            "type": "refresh",
        },
        get_settings().jwt_secret_key.get_secret_value(),
        algorithm=get_settings().jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)
