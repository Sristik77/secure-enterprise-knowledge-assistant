from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import verify_password
from app.main import app
from app.api.deps import require_roles
from app.models import Document, DocumentChunk, DocumentPermission, Role, User, UserRole


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
        expected_revision = "a13c8e6f4b21"
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

def test_database_role_grants_access(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    payload = registration_payload()
    response = integration_client.post("/auth/register", json=payload)
    assert response.status_code == 201

    user = integration_session.scalar(
        select(User).where(User.email == payload["email"])
    )
    assert user is not None

    role = Role(name=f"rbac_{uuid4().hex[:12]}")
    integration_session.add(role)
    integration_session.flush()

    integration_session.add(
        UserRole(user_id=user.id, role_id=role.id)
    )
    integration_session.flush()

    checker = require_roles(role.name)
    assert checker(current_user=user, db=integration_session) is user


def test_database_role_denies_user_without_membership(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    payload = registration_payload()
    response = integration_client.post("/auth/register", json=payload)
    assert response.status_code == 201

    user = integration_session.scalar(
        select(User).where(User.email == payload["email"])
    )
    assert user is not None

    checker = require_roles(f"missing_{uuid4().hex[:12]}")

    with pytest.raises(HTTPException) as exc_info:
        checker(current_user=user, db=integration_session)

    assert exc_info.value.status_code == 403


def test_admin_users_requires_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/admin/users")

    assert response.status_code == 401


def test_admin_users_forbids_user_without_admin_role(
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

    response = integration_client.get(
        "/admin/users",
        headers={
            "Authorization": f"Bearer {login.json()['access_token']}",
        },
    )

    assert response.status_code == 403


def test_admin_users_allows_admin_and_hides_password_hashes(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    payload = registration_payload()

    registration = integration_client.post("/auth/register", json=payload)
    assert registration.status_code == 201

    user = integration_session.scalar(
        select(User).where(User.email == payload["email"])
    )
    assert user is not None

    admin_role = integration_session.scalar(
        select(Role).where(Role.name == "admin")
    )
    if admin_role is None:
        admin_role = Role(name="admin")
        integration_session.add(admin_role)
        integration_session.flush()

    membership = UserRole(user_id=user.id, role_id=admin_role.id)
    integration_session.add(membership)
    integration_session.flush()

    login = integration_client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200

    response = integration_client.get(
        "/admin/users",
        headers={
            "Authorization": f"Bearer {login.json()['access_token']}",
        },
    )

    assert response.status_code == 200

    users = response.json()
    returned_user = next(
        item for item in users if item["email"] == payload["email"]
    )

    assert returned_user["full_name"] == payload["full_name"]
    assert "password_hash" not in returned_user
    assert all("password_hash" not in item for item in users)


def create_authenticated_test_user(
    client: TestClient,
    session: Session,
) -> tuple[dict[str, str], User, str]:
    """Register a test user and return its payload, database row, and JWT."""
    payload = registration_payload()

    registration = client.post("/auth/register", json=payload)
    assert registration.status_code == 201

    user = session.scalar(
        select(User).where(User.email == payload["email"])
    )
    assert user is not None

    login = client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200

    return payload, user, login.json()["access_token"]


def create_test_document(
    session: Session,
    owner: User,
    *,
    title: str = "Confidential test document",
) -> Document:
    """Create a document and a text chunk in the integration database."""
    document = Document(
        title=title,
        source_name=f"{title}.txt",
        content_type="text/plain",
        owner_id=owner.id,
        metadata_json={},
    )
    session.add(document)
    session.flush()

    session.add(
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="Confidential integration-test content.",
        )
    )
    session.flush()

    return document


def test_document_owner_can_list_and_read_document(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, owner, token = create_authenticated_test_user(
        integration_client, integration_session
    )
    document = create_test_document(integration_session, owner)

    headers = {"Authorization": f"Bearer {token}"}

    listing = integration_client.get("/documents", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == str(document.id) for item in listing.json())

    response = integration_client.get(
        f"/documents/{document.id}",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)
    assert response.json()["chunks"][0]["content"] == (
        "Confidential integration-test content."
    )
    assert "embedding" not in response.json()["chunks"][0]


def test_document_role_permission_grants_read_access(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, owner, _ = create_authenticated_test_user(
        integration_client, integration_session
    )
    _, reader, token = create_authenticated_test_user(
        integration_client, integration_session
    )
    document = create_test_document(integration_session, owner)

    role = Role(name=f"doc_reader_{uuid4().hex[:12]}")
    integration_session.add(role)
    integration_session.flush()

    integration_session.add(
        UserRole(user_id=reader.id, role_id=role.id)
    )
    integration_session.add(
        DocumentPermission(
            document_id=document.id,
            role_id=role.id,
            can_read=True,
        )
    )
    integration_session.flush()

    headers = {"Authorization": f"Bearer {token}"}

    listing = integration_client.get("/documents", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == str(document.id) for item in listing.json())

    response = integration_client.get(
        f"/documents/{document.id}",
        headers=headers,
    )
    assert response.status_code == 200


def test_user_without_permission_cannot_list_or_read_document(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, owner, _ = create_authenticated_test_user(
        integration_client, integration_session
    )
    _, reader, token = create_authenticated_test_user(
        integration_client, integration_session
    )
    document = create_test_document(integration_session, owner)

    headers = {"Authorization": f"Bearer {token}"}

    listing = integration_client.get("/documents", headers=headers)
    assert listing.status_code == 200
    assert all(item["id"] != str(document.id) for item in listing.json())

    response = integration_client.get(
        f"/documents/{document.id}",
        headers=headers,
    )
    assert response.status_code == 404


def test_document_permission_with_can_read_false_denies_access(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, owner, _ = create_authenticated_test_user(
        integration_client, integration_session
    )
    _, reader, token = create_authenticated_test_user(
        integration_client, integration_session
    )
    document = create_test_document(integration_session, owner)

    role = Role(name=f"doc_denied_{uuid4().hex[:12]}")
    integration_session.add(role)
    integration_session.flush()

    integration_session.add(
        UserRole(user_id=reader.id, role_id=role.id)
    )
    integration_session.add(
        DocumentPermission(
            document_id=document.id,
            role_id=role.id,
            can_read=False,
        )
    )
    integration_session.flush()

    response = integration_client.get(
        f"/documents/{document.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_multiple_roles_grant_access_if_any_role_allows_reading(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, owner, _ = create_authenticated_test_user(
        integration_client, integration_session
    )
    _, reader, token = create_authenticated_test_user(
        integration_client, integration_session
    )
    document = create_test_document(integration_session, owner)

    denied_role = Role(name=f"doc_no_{uuid4().hex[:12]}")
    allowed_role = Role(name=f"doc_yes_{uuid4().hex[:12]}")
    integration_session.add_all([denied_role, allowed_role])
    integration_session.flush()

    integration_session.add_all(
        [
            UserRole(user_id=reader.id, role_id=denied_role.id),
            UserRole(user_id=reader.id, role_id=allowed_role.id),
            DocumentPermission(
                document_id=document.id,
                role_id=denied_role.id,
                can_read=False,
            ),
            DocumentPermission(
                document_id=document.id,
                role_id=allowed_role.id,
                can_read=True,
            ),
        ]
    )
    integration_session.flush()

    response = integration_client.get(
        f"/documents/{document.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

def authenticated_user_token(client: TestClient) -> str:
    """Register a fresh user and return a valid access token."""
    payload = registration_payload()

    registration = client.post("/auth/register", json=payload)
    assert registration.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200

    return login.json()["access_token"]



def test_document_upload_persists_document_and_chunks(
    integration_client: TestClient,
    integration_session: Session,
    monkeypatch,
) -> None:
    """Verify uploaded documents and their embeddings are persisted."""
    from app.api import document_uploads

    monkeypatch.setattr(
        document_uploads,
        "embed_texts",
        lambda texts: [[0.01] * 384 for _ in texts],
    )

    token = authenticated_user_token(integration_client)

    response = integration_client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Integration Test Document"},
        files={
            "file": (
                "notes.txt",
                b"Enterprise security documentation for integration testing.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["title"] == "Integration Test Document"
    assert result["source_name"] == "notes.txt"
    assert len(result["chunks"]) == 1
    assert "Enterprise security documentation" in result["chunks"][0]["content"]

    stored_document = integration_session.get(Document, result["id"])
    assert stored_document is not None
    assert stored_document.owner_id == UUID(result["owner_id"])
    assert len(stored_document.chunks) == 1
    assert stored_document.chunks[0].chunk_index == 0

    stored_embedding = stored_document.chunks[0].embedding
    assert stored_embedding is not None
    assert len(stored_embedding) == 384


def test_document_upload_requires_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.post(
        "/documents",
        files={"file": ("notes.txt", b"Private document content.", "text/plain")},
    )

    assert response.status_code == 401


def test_document_upload_rejects_unsupported_file_type(
    integration_client: TestClient,
) -> None:
    token = authenticated_user_token(integration_client)

    response = integration_client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("payload.exe", b"not a supported document", "application/octet-stream")},
    )

    assert response.status_code == 415


def test_document_upload_rejects_empty_file(
    integration_client: TestClient,
) -> None:
    token = authenticated_user_token(integration_client)

    response = integration_client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 400


def test_document_upload_rejects_oversized_file(
    integration_client: TestClient,
) -> None:
    from app.services.document_ingestion import MAX_FILE_SIZE_BYTES

    token = authenticated_user_token(integration_client)

    response = integration_client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "file": (
                "large.txt",
                b"x" * (MAX_FILE_SIZE_BYTES + 1),
                "text/plain",
            )
        },
    )

    assert response.status_code == 413


def test_document_upload_does_not_persist_when_embedding_fails(
    integration_client: TestClient,
    integration_session: Session,
    monkeypatch,
) -> None:
    """A failed embedding operation must not save a partial document."""
    from app.api import document_uploads
    from app.services.embeddings import EmbeddingError

    def fail_embedding(texts):
        raise EmbeddingError("Simulated embedding failure")

    monkeypatch.setattr(document_uploads, "embed_texts", fail_embedding)

    token = authenticated_user_token(integration_client)
    documents_before = set(integration_session.scalars(select(Document.id)).all())

    response = integration_client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Must Not Be Saved"},
        files={
            "file": (
                "failure-test.txt",
                b"Testing embedding failure handling.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 503, response.text

    documents_after = set(integration_session.scalars(select(Document.id)).all())
    assert documents_after == documents_before


def test_document_upload_does_not_persist_when_embedding_fails(
    integration_client: TestClient,
    integration_session: Session,
    monkeypatch,
) -> None:
    """A failed embedding operation must not save a partial document."""
    from app.api import document_uploads
    from app.services.embeddings import EmbeddingError

    def fail_embedding(texts):
        raise EmbeddingError("Simulated embedding failure")

    monkeypatch.setattr(document_uploads, "embed_texts", fail_embedding)

    token = authenticated_user_token(integration_client)
    documents_before = set(integration_session.scalars(select(Document.id)).all())

    response = integration_client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Must Not Be Saved"},
        files={
            "file": (
                "failure-test.txt",
                b"Testing embedding failure handling.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 503, response.text

    documents_after = set(integration_session.scalars(select(Document.id)).all())
    assert documents_after == documents_before
