from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from api.main import create_app
from api.deps import get_db
from api.limiter import RateLimiter
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


def test_rate_limit_headers_in_response(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(review_route, "run_review", mock_task)

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    # incr returns 1, ttl returns 59
    mock_pipe.execute = AsyncMock(return_value=[1, 59])
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.aclose = AsyncMock()
    mock_redis.expire = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        r = client.post("/review", json={"diff": "--- a/foo.py\n+++ b/foo.py"})
        assert r.status_code == 202
        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
        assert "X-RateLimit-Reset" in r.headers
        assert r.headers["X-RateLimit-Limit"] == "10"
        assert r.headers["X-RateLimit-Remaining"] == "9"


def test_rate_limit_exceeded_returns_429(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(review_route, "run_review", mock_task)

    mock_redis = MagicMock()
    mock_pipe = MagicMock()
    # incr returns 11 (exceeds limit 10), ttl returns 45
    mock_pipe.execute = AsyncMock(return_value=[11, 45])
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.aclose = AsyncMock()
    mock_redis.expire = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        r = client.post("/review", json={"diff": "--- a/foo.py\n+++ b/foo.py"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert r.headers["Retry-After"] == "45"
        assert r.headers["X-RateLimit-Remaining"] == "0"
        assert "Rate limit exceeded" in r.json()["detail"]



def test_rate_limit_fails_open_on_redis_error(monkeypatch):
    mock_task = MagicMock()
    monkeypatch.setattr(review_route, "run_review", mock_task)

    with patch("redis.asyncio.from_url", side_effect=Exception("Redis unreachable")):
        r = client.post("/review", json={"diff": "--- a/foo.py\n+++ b/foo.py"})
        assert r.status_code == 202
        assert r.json()["status"] == "queued"
