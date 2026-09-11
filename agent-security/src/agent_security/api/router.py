"""Central API Router for Platform Endpoints."""

from fastapi import APIRouter
from agent_security.api.v1.health import router as health_router

api_router = APIRouter()

# Health endpoints available at both root and /v1
api_router.include_router(health_router)
