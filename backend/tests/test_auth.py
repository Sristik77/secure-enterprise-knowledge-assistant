
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import User


class FakeSession:
    """Small in-memory database substitute for authentication tests."""

    def __init__(self) -> None:
        self.lookup_user: User | None = None
        self.added_user: User | None = None

    def scalar(self, statement: Any) -> User | None:
        return self.lookup_user

    def add(self, user: User) -> None:
        self.added_user = user

    def commit(self) -> None:
        if self.added_user is not None:
            if self.added_user.id is None:
                self.added_user.id = uuid.uuid4()
            if self.added_user.is_active is None:
                self.added_user.is_active = True

    def refresh(self, user: User) -> None:
        pass

    def rollback(self) -> None:
        pass

    def get(self, model: type, user_id: uuid.UUID) -> User | None:
        if self.lookup_user is not None and self.lookup_user.id == user_id:
            return self.lookup_user
        return None


def make_user(
    *,
    email: str = "student@example.com",
    password: str = "Secure-Password-123!",
    is_active: bool = True,
) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        full_name="Student Name",
        is_active=is_active,
    )


@pytest.fixture
def db_session() -> Generator[FakeSession, None, None]:
    session = FakeSession()

    def override_get_db() -> Generator[FakeSession, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session: FakeSession) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def test_register_creates_user_with_hashed_password(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "Student@Example.com",
            "password": "Secure-Password-123!",
            "full_name": "Student Name",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    assert "password_hash" not in response.json()
    assert db_session.added_user is not None
    assert db_session.added_user.password_hash != "Secure-Password-123!"


def test_register_rejects_duplicate_email(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    db_session.lookup_user = make_user()

    response = client.post(
        "/auth/register",
        json={
            "email": "student@example.com",
            "password": "Secure-Password-123!",
            "full_name": "Another Student",
        },
    )

    assert response.status_code == 409


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "student@example.com",
            "password": "short",
            "full_name": "Student Name",
        },
    )

    assert response.status_code == 422


def test_login_returns_access_token(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    db_session.lookup_user = make_user()

    response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "Secure-Password-123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    db_session.lookup_user = make_user()

    response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "Wrong-Password-123!",
        },
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    db_session.lookup_user = make_user(is_active=False)

    response = client.post(
        "/auth/login",
        json={
            "email": "student@example.com",
            "password": "Secure-Password-123!",
        },
    )

    assert response.status_code == 403


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_authenticated_user(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    user = make_user()
    db_session.lookup_user = user
    token = create_access_token(user.id)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert response.json()["email"] == user.email
    assert "password_hash" not in response.json()


def test_me_rejects_inactive_user(
    client: TestClient,
    db_session: FakeSession,
) -> None:
    user = make_user(is_active=False)
    db_session.lookup_user = user
    token = create_access_token(user.id)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
