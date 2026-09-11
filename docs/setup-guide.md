# Local Environment & Deployment Setup Guide
## Autonomous AI Agent Security & Runtime Governance Platform

**Document Version:** 1.0.0  
**Phase:** Phase 1 (Project Foundation & Local Environment)  
**Status:** Verified Operational Baseline  

---

## 1. Quickstart with Docker Compose (Documented Local Command)

The entire platform (PostgreSQL 16, Redis 7, FastAPI In-Line Mediation Backend, and Next.js TypeScript Dashboard) can be brought up using a single command:

```bash
# 1. Create your local environment file from the secure example template
cp .env.example .env

# 2. Build and start all services
docker compose up --build
```

### Access Points:
- **FastAPI Backend Gateway**: `http://localhost:8000`
  - Liveness Probe: `http://localhost:8000/health/live`
  - Readiness Probe: `http://localhost:8000/health/ready`
  - Interactive API Documentation: `http://localhost:8000/docs` (development only)
- **Next.js Governance Dashboard**: `http://localhost:3000`
- **PostgreSQL Database**: `localhost:5432` (`agent_governance`)
- **Redis Cache & Budget Governor**: `localhost:6379`

---

## 2. Standalone Local Development (Without Docker)

### Prerequisites:
- Python 3.11+
- Node.js 20+ & npm 10+
- Running PostgreSQL and Redis instances (or use Docker for dependencies only)

```bash
# Start just the dependencies in Docker:
docker compose up postgres redis -d
```

### Backend Setup:
```bash
cd agent-security

# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
uv pip install -e ".[dev]" fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg redis alembic pydantic-settings httpx

# 3. Run database migrations
alembic upgrade head

# 4. Start the FastAPI development server
uvicorn agent_security.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup:
```bash
cd dashboard

# 1. Install dependencies
npm ci

# 2. Start the development dashboard server
npm run dev

# Or build and run the production optimized bundle:
npm run build
npm start
```

---

## 3. Database Schema Migrations (Alembic)

Database migrations use Alembic with async PostgreSQL support:

```bash
cd agent-security

# Check current migration revision:
alembic current

# Run all pending migrations:
alembic upgrade head

# Roll back the most recent migration:
alembic downgrade -1

# Generate a new auto-detected migration:
alembic revision --autogenerate -m "describe_schema_change"
```

---

## 4. Development vs. Production Configuration Safeguards

The platform enforces strict typed configuration validation (`agent_security.config.Settings`). **No insecure development defaults can silently apply in production:**

| Configuration Parameter | Development Mode (`ENVIRONMENT=development`) | Production Mode (`ENVIRONMENT=production`) | Invariant Violation Behavior |
| :--- | :--- | :--- | :--- |
| **`SECRET_KEY`** | Default dev key permitted with warning | Must be cryptographically random $\ge 32$ chars | **Fatal Startup Abort**: `ValueError` |
| **`DEBUG`** | Configurable (`true`/`false`) | Strictly must be `false` | **Fatal Startup Abort**: `ValueError` |
| **`CORS_ORIGINS`** | Localhost origins permitted | Explicit domains required, **no wildcards (`*`)** | **Fatal Startup Abort**: `ValueError` |
| **`DATABASE_URL`** | Local dev credentials allowed | Default `postgres:postgres` forbidden | **Fatal Startup Abort**: `ValueError` |
| **`ENABLE_FAIL_SECURE`** | Configurable (defaults to `true`) | Strictly must be `true` | **Fatal Startup Abort**: `ValueError` |
| **Interactive Docs (`/docs`)**| Enabled for rapid prototyping | Automatically disabled | Prevents schema leakage |

---

## 5. Verification & Test Execution

### Backend Automated Test Suite:
```bash
cd agent-security
pytest -v
```
*Current test suite verifies 46 automated invariant tests covering domain contracts, canonical hashing, state machine decoupling, decision synthesis, secret redaction, typed settings, liveness/readiness probes, and correlation middleware.*

### Frontend Verification:
```bash
cd dashboard
npm run lint
npm run build
```
