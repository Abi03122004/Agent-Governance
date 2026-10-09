"""Unit Tests for Correlation ID Middleware and Structured Error Responses."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from agent_security.main import create_app
from agent_security.config import Settings
from agent_security.middleware.correlation import HEADER_REQUEST_ID, HEADER_TRACE_ID


@pytest.fixture
def client():
    test_settings = Settings(
        ENVIRONMENT="testing",
        SECRET_KEY="test_secret_key_minimum_32_characters_long_123",
    )
    app = create_app(test_settings)

    # Add a test route requiring schema validation
    class Payload(BaseModel):
        name: str
        count: int

    @app.post("/test/validation")
    async def sample_endpoint(payload: Payload):
        return {"status": "ok", "name": payload.name}

    return TestClient(app)


def test_generates_correlation_headers_when_absent(client):
    """Verify that requests without correlation headers receive generated IDs."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert HEADER_REQUEST_ID in response.headers
    assert HEADER_TRACE_ID in response.headers
    assert response.headers[HEADER_REQUEST_ID].startswith("req_")
    assert response.headers[HEADER_TRACE_ID].startswith("trc_")


def test_propagates_incoming_correlation_headers(client):
    """Verify that incoming X-Request-ID and X-Trace-ID are preserved and returned."""
    custom_req_id = "req_custom_client_12345"
    custom_trc_id = "trc_custom_client_67890"

    headers = {
        HEADER_REQUEST_ID: custom_req_id,
        HEADER_TRACE_ID: custom_trc_id,
    }

    response = client.get("/health/live", headers=headers)
    assert response.status_code == 200
    assert response.headers[HEADER_REQUEST_ID] == custom_req_id
    assert response.headers[HEADER_TRACE_ID] == custom_trc_id


def test_structured_error_response_on_404(client):
    """Verify that 404 responses return a consistent structured error envelope."""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "HTTP_404"
    assert "Not Found" in error["message"]
    assert "request_id" in error
    assert "trace_id" in error


def test_structured_error_response_on_validation_failure(client):
    """Verify that payload validation errors return 422 with structured envelope."""
    response = client.post("/test/validation", json={"name": "test", "count": "not-an-integer"})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"] is not None
    assert "request_id" in error
    assert "trace_id" in error
