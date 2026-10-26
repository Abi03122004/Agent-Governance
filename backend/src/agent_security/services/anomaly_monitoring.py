"""Rule-based Anomaly Monitoring, Rate Tracking, and Repeated Denial Detection.

Provides:
1. Sliding window and fixed window rate counters in Redis (with in-memory fallback).
2. Repeated policy denial detection (triggers HIGH severity alert upon >= 3 blocks in 5 minutes).
3. Request rate spike detection (> 30 actions/min).
4. Direct WebSocket alert broadcasting to the governance dashboard.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from agent_security.services.redis import get_redis_client
from agent_security.services.realtime import ws_manager

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyAlertType(str, Enum):
    REPEATED_POLICY_DENIALS = "REPEATED_POLICY_DENIALS"
    RATE_SPIKE_DETECTED = "RATE_SPIKE_DETECTED"
    ANOMALOUS_SEQUENCE = "ANOMALOUS_SEQUENCE"
    INJECTION_PAYLOAD_DETECTED = "INJECTION_PAYLOAD_DETECTED"


@dataclass
class SecurityAlert:
    alert_id: str
    agent_id: str
    alert_type: AnomalyAlertType
    severity: AlertSeverity
    description: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "agent_id": self.agent_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class AnomalyMonitoringService:
    """Monitors runtime evaluations and tool usage, raising alerts on threshold violations."""

    MAX_ACTIONS_PER_MINUTE: int = 30
    MAX_DENIALS_THRESHOLD: int = 3
    DENIAL_WINDOW_SECONDS: int = 300
    RATE_WINDOW_SECONDS: int = 60

    # In-memory fallback structures when Redis is absent
    _mem_denials: Dict[str, List[float]] = {}
    _mem_rates: Dict[str, List[float]] = {}
    _mem_sequences: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    async def _use_redis(cls) -> bool:
        """Test if Redis is reachable."""
        try:
            client = get_redis_client()
            return await client.ping() is True
        except Exception:
            return False

    @classmethod
    async def record_action_attempt(
        cls,
        agent_id: str,
        decision: str,
        tool: str,
        operation: str,
    ) -> List[SecurityAlert]:
        """Record an action evaluation and evaluate anomaly rules."""
        now = time.time()
        alerts: List[SecurityAlert] = []

        # 1. Rate monitoring
        rate_count = await cls._increment_rate(agent_id, now)
        if rate_count > cls.MAX_ACTIONS_PER_MINUTE:
            alert = SecurityAlert(
                alert_id=f"alt_{uuid.uuid4().hex[:12]}",
                agent_id=agent_id,
                alert_type=AnomalyAlertType.RATE_SPIKE_DETECTED,
                severity=AlertSeverity.WARNING,
                description=f"Agent exceeded action rate limit: {rate_count} actions in {cls.RATE_WINDOW_SECONDS}s",
                metadata={"action_count": rate_count, "limit": cls.MAX_ACTIONS_PER_MINUTE},
            )
            alerts.append(alert)

        # 2. Repeated denial monitoring
        if decision in {"BLOCK", "SUSPEND"}:
            denial_count = await cls._increment_denial(agent_id, now)
            if denial_count >= cls.MAX_DENIALS_THRESHOLD:
                alert = SecurityAlert(
                    alert_id=f"alt_{uuid.uuid4().hex[:12]}",
                    agent_id=agent_id,
                    alert_type=AnomalyAlertType.REPEATED_POLICY_DENIALS,
                    severity=AlertSeverity.HIGH,
                    description=(
                        f"Repeated policy denials detected: {denial_count} actions blocked/suspended "
                        f"within {cls.DENIAL_WINDOW_SECONDS}s window. Agent suspension recommended."
                    ),
                    metadata={
                        "denial_count": denial_count,
                        "threshold": cls.MAX_DENIALS_THRESHOLD,
                        "window_seconds": cls.DENIAL_WINDOW_SECONDS,
                        "latest_tool": tool,
                        "latest_operation": operation,
                    },
                )
                alerts.append(alert)

        # Broadcast alerts in real time
        for a in alerts:
            try:
                await ws_manager.broadcast({
                    "type": "SECURITY_ALERT",
                    **a.to_dict(),
                })
            except Exception as e:
                logger.debug(f"Failed to broadcast websocket alert: {e}")

        return alerts

    @classmethod
    async def record_injection_threat(
        cls,
        agent_id: str,
        source_tool: str,
        scan_result_dict: Dict[str, Any],
    ) -> SecurityAlert:
        """Trigger an alert when indirect prompt injection or exfiltration triggers are detected."""
        alert = SecurityAlert(
            alert_id=f"alt_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            alert_type=AnomalyAlertType.INJECTION_PAYLOAD_DETECTED,
            severity=AlertSeverity.CRITICAL if scan_result_dict.get("risk_score", 0) > 0.8 else AlertSeverity.HIGH,
            description=f"Adversarial prompt injection or exfiltration trigger detected in output of '{source_tool}'.",
            metadata={
                "source_tool": source_tool,
                "threat_details": scan_result_dict,
            },
        )
        try:
            await ws_manager.broadcast({
                "type": "SECURITY_ALERT",
                **alert.to_dict(),
            })
        except Exception:
            pass
        return alert

    @classmethod
    async def _increment_rate(cls, agent_id: str, now: float) -> int:
        has_redis = await cls._use_redis()
        if has_redis:
            try:
                client = get_redis_client()
                key = f"rate:{agent_id}"
                pipe = client.pipeline()
                pipe.zadd(key, {str(now): now})
                pipe.zremrangebyscore(key, 0, now - cls.RATE_WINDOW_SECONDS)
                pipe.zcard(key)
                pipe.expire(key, cls.RATE_WINDOW_SECONDS + 10)
                results = await pipe.execute()
                return results[2]
            except Exception:
                pass

        # In-memory fallback
        timestamps = cls._mem_rates.setdefault(agent_id, [])
        timestamps.append(now)
        cls._mem_rates[agent_id] = [t for t in timestamps if t >= (now - cls.RATE_WINDOW_SECONDS)]
        return len(cls._mem_rates[agent_id])

    @classmethod
    async def _increment_denial(cls, agent_id: str, now: float) -> int:
        has_redis = await cls._use_redis()
        if has_redis:
            try:
                client = get_redis_client()
                key = f"denials:{agent_id}"
                pipe = client.pipeline()
                pipe.zadd(key, {str(now): now})
                pipe.zremrangebyscore(key, 0, now - cls.DENIAL_WINDOW_SECONDS)
                pipe.zcard(key)
                pipe.expire(key, cls.DENIAL_WINDOW_SECONDS + 10)
                results = await pipe.execute()
                return results[2]
            except Exception:
                pass

        # In-memory fallback
        timestamps = cls._mem_denials.setdefault(agent_id, [])
        timestamps.append(now)
        cls._mem_denials[agent_id] = [t for t in timestamps if t >= (now - cls.DENIAL_WINDOW_SECONDS)]
        return len(cls._mem_denials[agent_id])

    @classmethod
    async def get_agent_metrics(cls, agent_id: str) -> Dict[str, Any]:
        """Retrieve current sliding window counts for agent."""
        now = time.time()
        has_redis = await cls._use_redis()
        if has_redis:
            try:
                client = get_redis_client()
                rate_key = f"rate:{agent_id}"
                denials_key = f"denials:{agent_id}"
                rates = await client.zcount(rate_key, now - cls.RATE_WINDOW_SECONDS, "+inf")
                denials = await client.zcount(denials_key, now - cls.DENIAL_WINDOW_SECONDS, "+inf")
                return {
                    "actions_last_minute": rates,
                    "denials_last_5_minutes": denials,
                    "backend": "redis",
                }
            except Exception:
                pass

        rates = len([t for t in cls._mem_rates.get(agent_id, []) if t >= (now - cls.RATE_WINDOW_SECONDS)])
        denials = len([t for t in cls._mem_denials.get(agent_id, []) if t >= (now - cls.DENIAL_WINDOW_SECONDS)])
        return {
            "actions_last_minute": rates,
            "denials_last_5_minutes": denials,
            "backend": "in_memory",
        }

    @classmethod
    def reset_metrics(cls, agent_id: Optional[str] = None) -> None:
        """Clear memory counters for testing."""
        if agent_id:
            cls._mem_rates.pop(agent_id, None)
            cls._mem_denials.pop(agent_id, None)
        else:
            cls._mem_rates.clear()
            cls._mem_denials.clear()
