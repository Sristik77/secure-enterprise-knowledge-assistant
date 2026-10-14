from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_liveness_endpoint_returns_ok() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_document_has_expected_title() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert (
        response.json()["info"]["title"]
        == "Secure Enterprise Knowledge Assistant"
    )
