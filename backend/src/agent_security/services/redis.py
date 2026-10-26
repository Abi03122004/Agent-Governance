"""Async Redis Service for Rate Limiting, Budgets, and Distributed Caching."""

import logging
from typing import Optional
import redis.asyncio as aioredis
from redis.asyncio import Redis

from agent_security.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Retrieve or initialize the async Redis connection pool."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def check_redis_health() -> bool:
    """Execute a PING command to verify Redis connectivity."""
    try:
        client = get_redis_client()
        pong = await client.ping()
        return pong is True
    except Exception as exc:
        logger.warning(f"Redis readiness check failed: {exc}")
        return False


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        if hasattr(_redis_client, "aclose"):
            await _redis_client.aclose()
        else:
            await _redis_client.close()
        _redis_client = None
