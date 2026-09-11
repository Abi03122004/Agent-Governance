"""System Health, Liveness, and Readiness Service."""

from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from agent_security.db.session import check_db_health
from agent_security.services.redis import check_redis_health


async def evaluate_liveness() -> Dict[str, Any]:
    """Basic process liveness check."""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "agent-governance-platform",
    }


async def evaluate_readiness() -> Tuple[bool, Dict[str, Any]]:
    """Deep readiness check verifying essential external dependencies.
    
    Returns:
        Tuple[bool, Dict[str, Any]]: (is_ready, details)
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    is_ready = db_ok and redis_ok
    status_str = "healthy" if is_ready else "unhealthy"

    details = {
        "status": status_str,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "postgres": "healthy" if db_ok else "unhealthy",
            "redis": "healthy" if redis_ok else "unhealthy",
        },
    }
    return is_ready, details
