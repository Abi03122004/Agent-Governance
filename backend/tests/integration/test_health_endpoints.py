"""Unit Tests for Liveness and Readiness Probes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from agent_security.main import create_app
from agent_security.config import Settings


@pytest.fixture
def client():
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
    )
    app = create_app(test_settings)
    return TestClient(app)


def test_liveness_probe_returns_200_and_alive(client):
    """Verify liveness probe returns HTTP 200 with alive status."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data
    assert data["service"] == "agent-governance-platform"


@patch("agent_security.services.health.check_db_health", new_callable=AsyncMock)
@patch("agent_security.services.health.check_redis_health", new_callable=AsyncMock)
def test_readiness_probe_healthy_when_dependencies_up(mock_redis, mock_db, client):
    """Verify readiness returns HTTP 200 when both DB and Redis are healthy."""
    mock_db.return_value = True
    mock_redis.return_value = True

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["dependencies"]["postgres"] == "healthy"
    assert data["dependencies"]["redis"] == "healthy"


@patch("agent_security.services.health.check_db_health", new_callable=AsyncMock)
@patch("agent_security.services.health.check_redis_health", new_callable=AsyncMock)
def test_readiness_probe_fails_when_db_down(mock_redis, mock_db, client):
    """Readiness must reflect dependency health and return HTTP 503 if PostgreSQL is down."""
    mock_db.return_value = False
    mock_redis.return_value = True

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["dependencies"]["postgres"] == "unhealthy"
    assert data["dependencies"]["redis"] == "healthy"


@patch("agent_security.services.health.check_db_health", new_callable=AsyncMock)
@patch("agent_security.services.health.check_redis_health", new_callable=AsyncMock)
def test_readiness_probe_fails_when_redis_down(mock_redis, mock_db, client):
    """Readiness must reflect dependency health and return HTTP 503 if Redis is down."""
    mock_db.return_value = True
    mock_redis.return_value = False

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["dependencies"]["postgres"] == "healthy"
    assert data["dependencies"]["redis"] == "unhealthy"


@patch("agent_security.services.health.check_db_health", new_callable=AsyncMock)
@patch("agent_security.services.health.check_redis_health", new_callable=AsyncMock)
def test_readiness_probe_fails_when_both_down(mock_redis, mock_db, client):
    """Readiness returns HTTP 503 when both external dependencies are down."""
    mock_db.return_value = False
    mock_redis.return_value = False

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["dependencies"]["postgres"] == "unhealthy"
    assert data["dependencies"]["redis"] == "unhealthy"
