from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine


def test_database_connection_executes_query() -> None:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_session_factory_creates_session() -> None:
    with SessionLocal() as session:
        result = session.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_orm_base_has_metadata() -> None:
    assert Base.metadata is not None
