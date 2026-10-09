"""Typed Platform Configuration with Secure Production Enforcements."""

from typing import List, Literal, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentType = Literal["development", "staging", "production", "testing"]

DEFAULT_DEV_SECRET_KEY = "dev_insecure_secret_key_change_in_production_min32chars"
INSECURE_SECRETS = {
    DEFAULT_DEV_SECRET_KEY,
    "secret",
    "password",
    "changeme",
    "12345678",
    "admin",
}


class Settings(BaseSettings):
    """Platform configuration loaded from environment variables and .env files.
    
    Guarantees that no insecure development defaults silently pass in production.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Environment
    ENVIRONMENT: EnvironmentType = Field(default="development")
    DEBUG: bool = Field(default=False)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # Security & Cryptography
    SECRET_KEY: str = Field(default=DEFAULT_DEV_SECRET_KEY)
    SESSION_TOKEN_TTL_SECONDS: int = Field(default=3600, ge=60)
    EXECUTION_AUTH_TTL_SECONDS: int = Field(default=120, ge=30, le=900)
    APPROVAL_TICKET_TTL_SECONDS: int = Field(default=900, ge=60)  # 15 minutes default
    ENABLE_FAIL_SECURE: bool = Field(default=True)

    # Persistence & Caching
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/agent_governance"
    )
    DATABASE_POOL_SIZE: int = Field(default=10, ge=1)
    DATABASE_MAX_OVERFLOW: int = Field(default=20, ge=0)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(default=2.0)

    # Telemetry & Observability
    LOG_LEVEL: str = Field(default="INFO")
    SERVICE_NAME: str = Field(default="agent-governance-platform")
    CORS_ORIGINS: Union[List[str], str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def enforce_production_security_invariants(self) -> "Settings":
        """Strictly prevent insecure defaults from running in production."""
        if self.ENVIRONMENT == "production":
            # 1. Debug must never be true in production
            if self.DEBUG:
                raise ValueError("SECURITY VIOLATION: DEBUG cannot be True in production environment.")

            # 2. Secret Key must be strong and not default
            if self.SECRET_KEY in INSECURE_SECRETS or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECURITY VIOLATION: Insecure or default SECRET_KEY detected in production. "
                    "A strong secret of at least 32 characters is required."
                )

            # 3. CORS cannot be wildcard
            if "*" in self.CORS_ORIGINS:
                raise ValueError(
                    "SECURITY VIOLATION: Wildcard CORS_ORIGINS ('*') is strictly forbidden in production."
                )

            # 4. Fail-secure cannot be disabled in production
            if not self.ENABLE_FAIL_SECURE:
                raise ValueError(
                    "SECURITY VIOLATION: ENABLE_FAIL_SECURE must be True in production."
                )

            # 5. Database credentials must not use default dev credentials
            if "postgres:postgres" in self.DATABASE_URL:
                raise ValueError(
                    "SECURITY VIOLATION: Default database credentials (postgres:postgres) are not permitted in production."
                )

        return self


# Global singleton settings loader
_settings: Settings | None = None


def get_settings() -> Settings:
    """Retrieve or initialize the active Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_for_testing(new_settings: Settings | None = None) -> None:
    """Reset or override settings for isolated unit testing."""
    global _settings
    _settings = new_settings
