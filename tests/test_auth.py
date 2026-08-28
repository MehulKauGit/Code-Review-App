from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from api.main import create_app
from api.deps import get_db
import api.routes.review as review_route

app = create_app()

async def mock_get_db():
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result
    yield mock_session

app.dependency_overrides[get_db] = mock_get_db
client = TestClient(app)


def test_review_requires_auth_missing():
    r = client.post("/review", json={"diff": "--- a/foo.py\n+++ b/foo.py"})
    assert r.status_code == 401
    assert "Missing API Key" in r.json()["detail"]


def test_review_rejects_invalid_api_key():
    r = client.post(
        "/review",
        json={"diff": "--- a/foo.py\n+++ b/foo.py"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert r.status_code == 401
    assert "Invalid API Key" in r.json()["detail"]


def test_review_accepts_valid_header_api_key(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(review_route, "run_review", mock_task)

    r = client.post(
        "/review",
        json={"diff": "--- a/foo.py\n+++ b/foo.py"},
        headers={"X-API-Key": "dev-api-key"},
    )
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    assert "job_id" in r.json()


def test_review_accepts_valid_bearer_token(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(review_route, "run_review", mock_task)

    r = client.post(
        "/review",
        json={"diff": "--- a/foo.py\n+++ b/foo.py"},
        headers={"Authorization": "Bearer dev-api-key"},
    )
    assert r.status_code == 202
    assert r.json()["status"] == "queued"


def test_public_health_and_ready_endpoints_require_no_auth():
    health_resp = client.get("/health")
    assert health_resp.status_code == 200

    ready_resp = client.get("/ready")
    # Even if downstream services are unmocked, ready should return status (200 or 503), not 401
    assert ready_resp.status_code in [200, 503]
