# Multi-stage Dockerfile for Agent Security Runtime Governance Backend
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable package builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency specifications and source
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN uv pip install -e . "fastapi>=0.110.0" "uvicorn[standard]>=0.28.0" "sqlalchemy[asyncio]>=2.0.0" "asyncpg>=0.29.0" "redis>=5.0.0" "alembic>=1.13.0" "pydantic-settings>=2.0.0"

# Final runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime libpq
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Create unprivileged application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -d /app appuser

# Copy application source and migrations
COPY --chown=appuser:appgroup alembic.ini .
COPY --chown=appuser:appgroup migrations ./migrations
COPY --chown=appuser:appgroup src ./src

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "agent_security.main:app", "--host", "0.0.0.0", "--port", "8000"]
