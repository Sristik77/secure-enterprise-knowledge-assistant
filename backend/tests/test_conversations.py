
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message
from test_auth_integration import (
    integration_client,
    integration_session,
    registration_payload,
)



def register_and_login(client: TestClient) -> tuple[dict[str, str], str]:
    """Register a unique user and return their payload and access token."""
    payload = registration_payload()

    registration = client.post("/auth/register", json=payload)
    assert registration.status_code == 201, registration.text

    login = client.post(
        "/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )
    assert login.status_code == 200, login.text

    token = login.json()["access_token"]
    return payload, token



def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_conversations(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, token = register_and_login(integration_client)
    headers = auth_headers(token)

    created = integration_client.post(
        "/conversations",
        json={"title": "Security policy"},
        headers=headers,
    )

    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["title"] == "Security policy"
    conversation_id = UUID(conversation["id"])

    listing = integration_client.get("/conversations", headers=headers)

    assert listing.status_code == 200, listing.text
    listed_ids = {item["id"] for item in listing.json()}
    assert str(conversation_id) in listed_ids

    stored = integration_session.get(Conversation, conversation_id)
    assert stored is not None
    assert stored.title == "Security policy"


def test_conversation_requires_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/conversations")

    assert response.status_code in (401, 403)


def test_user_cannot_read_another_users_conversation(
    integration_client: TestClient,
) -> None:
    _, owner_token = register_and_login(integration_client)
    _, other_token = register_and_login(integration_client)

    created = integration_client.post(
        "/conversations",
        json={"title": "Private conversation"},
        headers=auth_headers(owner_token),
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    response = integration_client.get(
        f"/conversations/{conversation_id}",
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


def test_user_cannot_see_another_users_conversation_in_list(
    integration_client: TestClient,
) -> None:
    _, owner_token = register_and_login(integration_client)
    _, other_token = register_and_login(integration_client)

    created = integration_client.post(
        "/conversations",
        json={"title": "Owner-only conversation"},
        headers=auth_headers(owner_token),
    )
    assert created.status_code == 201, created.text
    owner_conversation_id = created.json()["id"]

    listing = integration_client.get(
        "/conversations",
        headers=auth_headers(other_token),
    )

    assert listing.status_code == 200, listing.text
    assert owner_conversation_id not in {
        item["id"] for item in listing.json()
    }


def test_conversation_detail_returns_persisted_messages(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, token = register_and_login(integration_client)
    headers = auth_headers(token)

    created = integration_client.post(
        "/conversations",
        json={"title": "Message history"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    conversation_id = UUID(created.json()["id"])

    citations = [
        {
            "document_id": "00000000-0000-0000-0000-000000000001",
            "document_title": "Security Policy",
            "source_name": "security-policy.pdf",
            "chunk_index": 0,
            "similarity": 0.92,
        }
    ]

    conversation = integration_session.get(Conversation, conversation_id)
    assert conversation is not None

    integration_session.add_all(
        [
            Message(
                conversation_id=conversation_id,
                role="user",
                content="What is the policy?",
                citations=[],
            ),
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content="The policy is documented here.",
                citations=citations,
            ),
        ]
    )
    integration_session.flush()

    response = integration_client.get(
        f"/conversations/{conversation_id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(conversation_id)
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "What is the policy?"
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][1]["citations"] == citations
def test_owner_can_rename_conversation(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, token = register_and_login(integration_client)
    headers = auth_headers(token)

    created = integration_client.post(
        "/conversations",
        json={"title": "Old title"},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    conversation_id = UUID(created.json()["id"])

    response = integration_client.patch(
        f"/conversations/{conversation_id}",
        json={"title": "  Updated title  "},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated title"

    stored = integration_session.get(Conversation, conversation_id)
    assert stored is not None
    assert stored.title == "Updated title"


def test_rename_rejects_blank_title(
    integration_client: TestClient,
) -> None:
    _, token = register_and_login(integration_client)
    headers = auth_headers(token)

    created = integration_client.post(
        "/conversations",
        json={"title": "Keep this title"},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    response = integration_client.patch(
        f"/conversations/{created.json()['id']}",
        json={"title": "   "},
        headers=headers,
    )

    assert response.status_code == 422


def test_user_cannot_rename_another_users_conversation(
    integration_client: TestClient,
) -> None:
    _, owner_token = register_and_login(integration_client)
    _, other_token = register_and_login(integration_client)

    created = integration_client.post(
        "/conversations",
        json={"title": "Owner title"},
        headers=auth_headers(owner_token),
    )
    assert created.status_code == 201, created.text

    response = integration_client.patch(
        f"/conversations/{created.json()['id']}",
        json={"title": "Unauthorized change"},
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."

    owner_listing = integration_client.get(
        "/conversations",
        headers=auth_headers(owner_token),
    )
    assert owner_listing.status_code == 200
    assert owner_listing.json()[0]["title"] == "Owner title"


def test_rename_requires_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.patch(
        "/conversations/00000000-0000-0000-0000-000000000001",
        json={"title": "Unauthorized"},
    )

    assert response.status_code in (401, 403)


def test_owner_can_delete_conversation_and_messages(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, token = register_and_login(integration_client)
    headers = auth_headers(token)

    created = integration_client.post(
        "/conversations",
        json={"title": "Conversation to delete"},
        headers=headers,
    )
    assert created.status_code == 201, created.text

    conversation_id = UUID(created.json()["id"])

    conversation = integration_session.get(
        Conversation, conversation_id
    )
    assert conversation is not None

    message = Message(
        conversation_id=conversation_id,
        role="user",
        content="Test message",
        citations=[],
    )
    integration_session.add(message)
    integration_session.flush()
    message_id = message.id

    response = integration_client.delete(
        f"/conversations/{conversation_id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert integration_session.get(Conversation, conversation_id) is None
    assert integration_session.get(Message, message_id) is None


def test_user_cannot_delete_another_users_conversation(
    integration_client: TestClient,
    integration_session: Session,
) -> None:
    _, owner_token = register_and_login(integration_client)
    _, other_token = register_and_login(integration_client)

    created = integration_client.post(
        "/conversations",
        json={"title": "Keep this conversation"},
        headers=auth_headers(owner_token),
    )
    assert created.status_code == 201, created.text

    conversation_id = UUID(created.json()["id"])

    response = integration_client.delete(
        f"/conversations/{conversation_id}",
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."

    stored = integration_session.get(Conversation, conversation_id)
    assert stored is not None
    assert stored.title == "Keep this conversation"


def test_delete_requires_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.delete(
        "/conversations/00000000-0000-0000-0000-000000000001",
    )

    assert response.status_code in (401, 403)