"""Health, Liveness, and Readiness Endpoints."""

from fastapi import APIRouter, Response, status
from agent_security.services.health import evaluate_liveness, evaluate_readiness

router = APIRouter(tags=["Health & Diagnostics"])


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Returns 200 if the process is up and running.",
    status_code=status.HTTP_200_OK,
)
async def liveness_probe():
    return await evaluate_liveness()


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Returns 200 if database and cache dependencies are healthy, else 503.",
)
async def readiness_probe(response: Response):
    is_ready, details = await evaluate_readiness()
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        response.status_code = status.HTTP_200_OK
    return details
