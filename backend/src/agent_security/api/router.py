"""Central API Router for Platform Endpoints."""

from fastapi import APIRouter
from agent_security.api.v1.health import router as health_router
from agent_security.api.v1.organizations import router as orgs_router
from agent_security.api.v1.projects import router as projects_router
from agent_security.api.v1.users import router as users_router
from agent_security.api.v1.agents import router as agents_router
from agent_security.api.v1.sessions import router as sessions_router
from agent_security.api.v1.runtime import router as runtime_router
from agent_security.api.v1.monitoring import router as monitoring_router
from agent_security.api.v1.approvals import router as approvals_router
from agent_security.api.v1.audit import router as audit_router

api_router = APIRouter()

# Health endpoints
api_router.include_router(health_router)

# Versioned /api/v1 endpoints
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(orgs_router)
v1_router.include_router(projects_router)
v1_router.include_router(users_router)
v1_router.include_router(agents_router)
v1_router.include_router(sessions_router)
v1_router.include_router(runtime_router)
v1_router.include_router(approvals_router)
v1_router.include_router(monitoring_router)
v1_router.include_router(audit_router)
api_router.include_router(v1_router)

# Direct mounts for backwards compatibility
api_router.include_router(orgs_router)
api_router.include_router(projects_router)
api_router.include_router(users_router)
api_router.include_router(agents_router)
api_router.include_router(sessions_router)
api_router.include_router(runtime_router)
api_router.include_router(approvals_router)
api_router.include_router(monitoring_router)
api_router.include_router(audit_router)
