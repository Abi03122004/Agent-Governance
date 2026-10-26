"""Durable, tamper-evident audit service with hash-chaining and redaction."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.core.redaction import redact_sensitive_payload
from agent_security.db.models.runtime_activity import AuditEventModel
from agent_security.services.realtime import ws_manager


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AuditService:
    @staticmethod
    def compute_hash(
        previous_event_hash: Optional[str],
        event_id: str,
        organization_id: str,
        event_type: str,
        timestamp: datetime,
        details: Dict[str, Any],
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        action_id: Optional[str] = None,
        policy_decision: Optional[str] = None,
        execution_state: Optional[str] = None,
    ) -> str:
        """Deterministic SHA-256 hash chaining over audit event metadata and sanitized payload."""
        payload_repr = {
            "previous_event_hash": previous_event_hash or "",
            "event_id": event_id,
            "organization_id": organization_id,
            "event_type": event_type,
            "agent_id": agent_id or "",
            "session_id": session_id or "",
            "action_id": action_id or "",
            "policy_decision": policy_decision or "",
            "execution_state": execution_state or "",
            "timestamp": timestamp.isoformat(),
            "details": details,
        }
        serialized = json.dumps(payload_repr, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    async def record_event(
        cls,
        db: AsyncSession,
        organization_id: str,
        event_type: str,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        action_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        canonical_action_hash: Optional[str] = None,
        policy_decision: Optional[str] = "N/A",
        execution_state: Optional[str] = "N/A",
        severity: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEventModel:
        """Record an immutable, hash-chained, sanitized audit event for a tenant."""
        # 1. Fetch previous event hash for tenant
        prev_stmt = (
            select(AuditEventModel.event_hash)
            .where(AuditEventModel.organization_id == organization_id)
            .order_by(AuditEventModel.timestamp.desc(), AuditEventModel.event_id.desc())
            .limit(1)
        )
        prev_result = await db.execute(prev_stmt)
        previous_event_hash = prev_result.scalar_one_or_none()

        # 2. Scrub sensitive data from payload
        sanitized_details = redact_sensitive_payload(details or {})
        if not isinstance(sanitized_details, dict):
            sanitized_details = {"raw": sanitized_details}

        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        # 3. Compute hash chain
        event_hash = cls.compute_hash(
            previous_event_hash=previous_event_hash,
            event_id=event_id,
            organization_id=organization_id,
            event_type=event_type,
            timestamp=now,
            details=sanitized_details,
            agent_id=agent_id,
            session_id=session_id,
            action_id=action_id,
            policy_decision=policy_decision,
            execution_state=execution_state,
        )

        # 4. Persist event
        event = AuditEventModel(
            event_id=event_id,
            organization_id=organization_id,
            project_id=project_id or "",
            agent_id=agent_id or "",
            session_id=session_id or "",
            task_id=task_id or "",
            action_id=action_id or "",
            tool_name=tool_name or "",
            canonical_action_hash=canonical_action_hash or "",
            policy_decision=policy_decision or "N/A",
            execution_state=execution_state or "N/A",
            severity=severity,
            event_type=event_type,
            details=sanitized_details,
            previous_event_hash=previous_event_hash,
            event_hash=event_hash,
            timestamp=now,
        )
        db.add(event)
        await db.flush()

        # 5. Broadcast to realtime dashboard subscribers
        try:
            await ws_manager.broadcast({
                "type": "audit_event",
                "event_id": event_id,
                "organization_id": organization_id,
                "event_type": event_type,
                "agent_id": agent_id,
                "severity": severity,
                "timestamp": now.isoformat(),
                "policy_decision": policy_decision,
                "execution_state": execution_state,
            })
        except Exception:
            pass

        return event

    @classmethod
    async def verify_chain(
        cls,
        db: AsyncSession,
        organization_id: str,
    ) -> Tuple[bool, int, Optional[str]]:
        """Verify the cryptographic hash chain integrity for an organization's audit log.
        Returns (is_valid, verified_count, error_reason).
        """
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.organization_id == organization_id)
            .order_by(AuditEventModel.timestamp.asc(), AuditEventModel.event_id.asc())
        )
        result = await db.execute(stmt)
        events: List[AuditEventModel] = result.scalars().all()

        if not events:
            return True, 0, None

        expected_prev_hash: Optional[str] = None
        for idx, evt in enumerate(events):
            if evt.previous_event_hash != expected_prev_hash:
                return False, idx, f"Broken chain at event {evt.event_id}: expected prev {expected_prev_hash}, got {evt.previous_event_hash}"

            recomputed_hash = cls.compute_hash(
                previous_event_hash=evt.previous_event_hash,
                event_id=evt.event_id,
                organization_id=evt.organization_id,
                event_type=evt.event_type,
                timestamp=_to_utc(evt.timestamp),
                details=evt.details or {},
                agent_id=evt.agent_id,
                session_id=evt.session_id,
                action_id=evt.action_id,
                policy_decision=evt.policy_decision,
                execution_state=evt.execution_state,
            )
            if recomputed_hash != evt.event_hash:
                return False, idx, f"Hash mismatch at event {evt.event_id}: calculated {recomputed_hash}, stored {evt.event_hash}"

            expected_prev_hash = evt.event_hash

        return True, len(events), None
