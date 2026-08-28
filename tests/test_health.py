from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from api.main import create_app

client = TestClient(create_app())


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_readiness_all_healthy():
    with patch("api.main.check_database", new_callable=AsyncMock) as mock_db, \
         patch("api.main.check_redis", new_callable=AsyncMock) as mock_redis:
        mock_db.return_value = (True, None)
        mock_redis.return_value = (True, None)

        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"]["status"] == "healthy"
        assert data["checks"]["redis"]["status"] == "healthy"


def test_readiness_database_failure():
    with patch("api.main.check_database", new_callable=AsyncMock) as mock_db, \
         patch("api.main.check_redis", new_callable=AsyncMock) as mock_redis:
        mock_db.return_value = (False, "Connection timeout")
        mock_redis.return_value = (True, None)

        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "unhealthy"
        assert data["checks"]["database"]["error"] == "Connection timeout"
        assert data["checks"]["redis"]["status"] == "healthy"


def test_readiness_redis_failure():
    with patch("api.main.check_database", new_callable=AsyncMock) as mock_db, \
         patch("api.main.check_redis", new_callable=AsyncMock) as mock_redis:
        mock_db.return_value = (True, None)
        mock_redis.return_value = (False, "Redis connection refused")

        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "healthy"
        assert data["checks"]["redis"]["status"] == "unhealthy"
        assert data["checks"]["redis"]["error"] == "Redis connection refused"
