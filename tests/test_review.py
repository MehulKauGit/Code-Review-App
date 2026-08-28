from unittest.mock import AsyncMock, patch
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
client = TestClient(app, headers={"X-API-Key": "dev-api-key"})


def test_review_rejects_empty_payload():
    r = client.post("/review", json={})
    assert r.status_code == 422

def test_review_rejects_missing_diff_and_content():
    r = client.post("/review", json={"repo": "owner/repo"})
    assert r.status_code == 422

def test_review_accepts_diff(monkeypatch):
    from unittest.mock import MagicMock
    mock_task = MagicMock()
    monkeypatch.setattr(review_route, "run_review", mock_task)
    r = client.post("/review", json={"diff": "--- a/foo.py\n+++ b/foo.py"})
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    assert "job_id" in r.json()
    assert mock_task.apply_async.called

