"""Unit Tests for Typed Settings and Production Security Invariants."""

import pytest
from pydantic import ValidationError
from agent_security.config import Settings, DEFAULT_DEV_SECRET_KEY


def test_development_config_loads_defaults():
    """Verify default development configuration loads with safe development values."""
    settings = Settings(
        ENVIRONMENT="development",
        SECRET_KEY=DEFAULT_DEV_SECRET_KEY,
    )
    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is False
    assert settings.ENABLE_FAIL_SECURE is True


def test_production_rejects_default_secret_key():
    """Security Invariant: Production MUST fail to start if default secret key is used."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=DEFAULT_DEV_SECRET_KEY,
            DATABASE_URL="postgresql+asyncpg://admin:secure_password_123@prod-db:5432/agent_gov",
        )
    assert "Insecure or default SECRET_KEY detected in production" in str(excinfo.value)


def test_production_rejects_short_secret_key():
    """Security Invariant: Production secret key must be at least 32 characters."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="too_short_secret",
            DATABASE_URL="postgresql+asyncpg://admin:secure_password_123@prod-db:5432/agent_gov",
        )
    assert "at least 32 characters is required" in str(excinfo.value)


def test_production_rejects_debug_true():
    """Security Invariant: DEBUG cannot be True in production."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://admin:secure_password_123@prod-db:5432/agent_gov",
        )
    assert "DEBUG cannot be True in production" in str(excinfo.value)


def test_production_rejects_wildcard_cors():
    """Security Invariant: Wildcard CORS is forbidden in production."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://admin:secure_password_123@prod-db:5432/agent_gov",
            CORS_ORIGINS=["*"],
        )
    assert "Wildcard CORS_ORIGINS ('*') is strictly forbidden" in str(excinfo.value)


def test_production_rejects_default_postgres_credentials():
    """Security Invariant: Default postgres:postgres credentials forbidden in production."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@prod-db:5432/agent_gov",
        )
    assert "Default database credentials" in str(excinfo.value)


def test_production_accepts_hardened_config():
    """Verify that a compliant production configuration succeeds."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY="very_strong_production_secret_key_1234567890!",
        DATABASE_URL="postgresql+asyncpg://corp_app:Strong_Pass_987#@prod-db.internal:5432/agent_gov",
        CORS_ORIGINS=["https://governance.corp.com"],
        ENABLE_FAIL_SECURE=True,
        ALLOW_DEV_HEADER_AUTH=False,
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False
    assert len(settings.SECRET_KEY) >= 32
    assert settings.ALLOW_DEV_HEADER_AUTH is False


def test_production_rejects_allow_dev_header_auth():
    """Security Invariant: Insecure dev header auth must fail to start in production."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            ALLOW_DEV_HEADER_AUTH=True,
            SECRET_KEY="a" * 32,
            DATABASE_URL="postgresql+asyncpg://admin:secure_password_123@prod-db:5432/agent_gov",
        )
    assert "Insecure development header authentication" in str(excinfo.value)

