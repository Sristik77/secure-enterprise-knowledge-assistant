from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import verify_password
from app.main import app
from app.models import User


TEST_DATABASE = "secure_knowledge_assistant_test"


@pytest.fixture
def integration_session() -> Generator[Session, None, None]:
    settings = get_settings()
    test_url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=TEST_DATABASE,
    )

    test_engine = create_engine(test_url, poolclass=NullPool)
    connection = test_engine.connect()
    transaction = None
    session = None
    previous_overrides = app.dependency_overrides.copy()

    try:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()
        if database_name != TEST_DATABASE:
            raise RuntimeError(
                f"Refusing to run tests against {database_name!r}"
            )

        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
        expected_revision = "256fb3c7f951"
        if revision != expected_revision:
            raise RuntimeError(
                f"Expected Alembic revision {expected_revision!r}, "
                f"got {revision!r}"
            )

        # Finish the read-only inspection transaction before starting
        # the rollback-protected transaction used by the tests.
        connection.commit()
        transaction = connection.begin()
        TestingSession = sessionmaker(
            bind=connection,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        session = TestingSession()

        def override_get_db() -> Generator[Session, None, None]:
            yield session

        app.dependency_overrides[get_db] = override_get_db
        yield session

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if session is not None:
            session.close()
        if transaction is not None and transaction.is_active:
            transaction.rollback()
        connection.close()
        test_engine.dispose()


@pytest.fixture
def integration_client(
    integration_session: Session,
) -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


def registration_payload() -> dict[str, str]:
    return {
        "email": f"{uuid4().hex}@example.com",
        "password": "Integration-Test-Password-123!",
        "full_name": "Integration Test User",
    }


def test_registration_persists_hashed_password(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    payload = registration_payload()
    response = integration_client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]
    assert "password_hash" not in response.json()

    stored_user = integration_session.scalar(
        select(User).where(User.email == payload["email"])
    )
    assert stored_user is not None
    assert stored_user.password_hash != payload["password"]
    assert verify_password(payload["password"], stored_user.password_hash)


def test_registration_rejects_duplicate_email(
    integration_client: TestClient,
) -> None:
    payload = registration_payload()

    first = integration_client.post("/auth/register", json=payload)
    second = integration_client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_token_authenticates_persisted_user(
    integration_client: TestClient,
) -> None:
    payload = registration_payload()
    registration = integration_client.post("/auth/register", json=payload)
    assert registration.status_code == 201

    login = integration_client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"

    profile = integration_client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {login.json()['access_token']}"
        },
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == payload["email"]
    assert profile.json()["full_name"] == payload["full_name"]
    assert "password_hash" not in profile.json()


def test_login_rejects_wrong_password(
    integration_client: TestClient,
) -> None:
    payload = registration_payload()
    registration = integration_client.post("/auth/register", json=payload)
    assert registration.status_code == 201

    response = integration_client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": "Incorrect-Password-123!",
        },
    )
    assert response.status_code == 401
