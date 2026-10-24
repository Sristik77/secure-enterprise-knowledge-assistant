
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app


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

        expected_revision = "26ca750b8d1a"
        if revision != expected_revision:
            raise RuntimeError(
                f"Expected Alembic revision {expected_revision!r}, "
                f"got {revision!r}"
            )

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
