"""Provider-neutral, pre-side-effect runtime gateway endpoints."""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.config import get_settings
from agent_security.core.redaction import redact_sensitive_data
from agent_security.db.models import (
    AgentModel,
    AgentSessionModel,
    ApprovalRequestModel,
    ExecutionAuthorizationModel,
    LLMPendingRequestModel,
    OrganizationModel,
    ProjectModel,
    RuntimeActionModel,
)
from agent_security.db.session import get_db
from agent_security.domain.identity import AgentIdentity
from agent_security.domain.runtime import ExecuteActionRequest, ReportResultRequest, RuntimeActionInput, RuntimeActivity, RuntimeDecision
from agent_security.middleware.auth import authenticate_agent_async
from agent_security.services.runtime_gateway import AuthenticatedAgent, RuntimeGateway, StoredAction
from agent_security.runtime.authorization import canonical_result_hash
from agent_security.services.realtime import ws_manager
from agent_security.services.audit_service import AuditService
from agent_security.security.injection_defense import InjectionDetector
from agent_security.services.anomaly_monitoring import AnomalyMonitoringService

router = APIRouter(prefix="/runtime", tags=["Runtime"])


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def gateway() -> RuntimeGateway:
    settings = get_settings()
    return RuntimeGateway(settings.SECRET_KEY, settings.EXECUTION_AUTH_TTL_SECONDS)


def identity_from(agent: AgentIdentity) -> AuthenticatedAgent:
    return AuthenticatedAgent(agent.organization_id, agent.project_id, agent.id, agent.status)


async def owned_session(db: AsyncSession, session_id: str, agent: AgentIdentity) -> AgentSessionModel:
    row = await db.execute(select(AgentSessionModel).where(
        AgentSessionModel.session_id == session_id,
        AgentSessionModel.agent_id == agent.id,
        AgentSessionModel.organization_id == agent.organization_id,
        AgentSessionModel.project_id == agent.project_id,
        AgentSessionModel.status == "active",
    ))
    session = row.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active session not found for authenticated agent")
    exp = _to_utc(session.expires_at)
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Session expired")
    return session


def stored_action(row: RuntimeActionModel) -> StoredAction:
    identity = AuthenticatedAgent(row.organization_id, row.project_id, row.agent_id, "active")
    return StoredAction(row.id, identity, row.session_id, row.normalized_action, row.action_digest,
                        row.decision, row.correlation_id, row.created_at)


@router.post("/sessions", status_code=status.HTTP_201_CREATED, tags=["Runtime"])
async def start_runtime_session(
    expires_in_seconds: int | None = None,
    db: AsyncSession = Depends(get_db), agent: AgentIdentity = Depends(authenticate_agent_async),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    if agent.status == "suspended":
        raise HTTPException(status_code=403, detail="Suspended agent cannot start runtime session")
    if agent.status != "active":
        raise HTTPException(status_code=403, detail="Inactive agent cannot start runtime session")
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    expires_at = (now + timedelta(seconds=expires_in_seconds)) if expires_in_seconds else None
    session = AgentSessionModel(
        session_id="sess_" + uuid.uuid4().hex, organization_id=agent.organization_id,
        project_id=agent.project_id, agent_id=agent.id, status="active", correlation_id=correlation_id,
        expires_at=expires_at,
    )
    db.add(session)
    await db.execute(
        update(AgentModel)
        .where(AgentModel.id == agent.id)
        .values(
            connection_status="connected",
            last_seen_at=now,
            governed_requests_count=AgentModel.governed_requests_count + 1,
        )
    )
    await db.commit()
    return {"session_id": session.session_id, "organization_id": agent.organization_id,
            "project_id": agent.project_id, "agent_id": agent.id, "status": "active",
            "expires_at": session.expires_at}


@router.get("/sessions", tags=["Runtime"])
async def list_runtime_sessions(
    organization_id: str | None = None,
    agent_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List runtime sessions (supports GET /api/v1/runtime/sessions)."""
    stmt = select(AgentSessionModel)
    if organization_id:
        stmt = stmt.where(AgentSessionModel.organization_id == organization_id)
    if agent_id:
        stmt = stmt.where(AgentSessionModel.agent_id == agent_id)
    result = await db.execute(stmt.order_by(AgentSessionModel.started_at.desc()))
    rows = result.scalars().all()
    return [
        {
            "session_id": s.session_id,
            "organization_id": s.organization_id,
            "project_id": s.project_id,
            "agent_id": s.agent_id,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in rows
    ]


@router.post("/actions/evaluate", response_model=RuntimeDecision)
async def evaluate_action(
    request: RuntimeActionInput, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    # 0. Anti-Spoofing: Strictly validate agent-supplied identity against authenticated token
    if request.agent_id and request.agent_id != agent.id:
        raise HTTPException(
            status_code=403,
            detail=f"Identity mismatch: request agent_id '{request.agent_id}' does not match authenticated agent '{agent.id}'",
        )
    if request.organization_id and request.organization_id != agent.organization_id:
        raise HTTPException(
            status_code=403,
            detail=f"Tenant mismatch: request organization_id '{request.organization_id}' does not match authenticated organization '{agent.organization_id}'",
        )

    await owned_session(db, request.session_id, agent)

    # 1. Organization & Project scope suspension checks
    org_res = await db.execute(select(OrganizationModel).where(OrganizationModel.id == agent.organization_id))
    org_rec = org_res.scalar_one_or_none()
    if org_rec and org_rec.status == "suspended":
        raise HTTPException(status_code=403, detail="Organization is suspended")

    proj_res = await db.execute(select(ProjectModel).where(ProjectModel.id == agent.project_id))
    proj_rec = proj_res.scalar_one_or_none()
    if proj_rec and proj_rec.status == "suspended":
        raise HTTPException(status_code=403, detail="Project is suspended")

    correlation_id = correlation_id or request.request_id or "req_" + uuid.uuid4().hex
    service = gateway()
    action, decision = service.evaluate(identity_from(agent), request, correlation_id)
    if request.request_id:
        decision.request_id = request.request_id
    
    exec_status = "EVALUATED"
    if decision.decision == "ALLOW":
        exec_status = "ALLOWED"
    elif decision.decision == "BLOCK":
        exec_status = "BLOCKED"
    elif decision.decision == "REQUIRE_APPROVAL":
        exec_status = "AWAITING_APPROVAL"
    elif decision.decision == "SUSPEND":
        exec_status = "SUSPENDED"

    record = RuntimeActionModel(
        id=action.action_id, organization_id=agent.organization_id, project_id=agent.project_id,
        agent_id=agent.id, session_id=request.session_id, tool=action.normalized["tool"],
        operation=action.normalized["operation"], resource=action.normalized["resource"],
        normalized_action=action.normalized, action_digest=action.digest, decision=decision.decision,
        reason_code=decision.reason_code, correlation_id=correlation_id,
        execution_status=exec_status,
    )
    db.add(record)
    await db.flush()

    if decision.decision == "REQUIRE_APPROVAL":
        from datetime import timedelta
        approval_ticket_id = "appr_" + uuid.uuid4().hex
        ticket_ttl = get_settings().APPROVAL_TICKET_TTL_SECONDS
        ticket_expires_at = datetime.now(timezone.utc) + timedelta(seconds=ticket_ttl)
        ticket = ApprovalRequestModel(
            ticket_id=approval_ticket_id,
            organization_id=agent.organization_id,
            action_id=action.action_id,
            canonical_action_hash=action.digest,
            status="PENDING",
            expires_at=ticket_expires_at,
        )
        db.add(ticket)
        decision.approval_ticket_id = approval_ticket_id

    if decision.execution_authorization and decision.execution_authorization_expires_at:
        db.add(ExecutionAuthorizationModel(
            id="auth_" + uuid.uuid4().hex, action_id=action.action_id,
            token_hash=hashlib.sha256(decision.execution_authorization.encode()).hexdigest(),
            expires_at=decision.execution_authorization_expires_at,
        ))
    await AuditService.record_event(
        db,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        session_id=request.session_id,
        action_id=action.action_id,
        tool_name=action.normalized.get("tool", ""),
        canonical_action_hash=action.digest,
        policy_decision=decision.decision,
        execution_state=exec_status,
        severity="WARN" if decision.decision in ["BLOCK", "SUSPEND"] else "INFO",
        event_type="action.evaluated",
        details={
            "tool": action.normalized.get("tool"),
            "operation": action.normalized.get("operation"),
            "resource": action.normalized.get("resource"),
            "reason_code": decision.reason_code,
            "arguments": action.normalized.get("arguments", {}),
        },
    )
    await db.execute(
        update(AgentModel)
        .where(AgentModel.id == agent.id)
        .values(
            connection_status="connected",
            last_seen_at=datetime.now(timezone.utc),
            governed_requests_count=AgentModel.governed_requests_count + 1,
        )
    )
    await db.commit()

    # Broadcast evaluation to WebSocket listeners
    await ws_manager.broadcast({
        "type": "ACTION_EVALUATED",
        "action_id": action.action_id,
        "organization_id": agent.organization_id,
        "project_id": agent.project_id,
        "agent_id": agent.id,
        "session_id": request.session_id,
        "tool": action.normalized["tool"],
        "operation": action.normalized["operation"],
        "resource": action.normalized["resource"],
        "decision": decision.decision,
        "reason_code": decision.reason_code,
        "execution_status": exec_status,
        "action_digest": action.digest,
        "correlation_id": correlation_id,
        "timestamp": record.created_at,
    })

    # Track in anomaly monitoring service (rate, repeated denials, sequence alerts)
    await AnomalyMonitoringService.record_action_attempt(
        agent_id=agent.id,
        decision=decision.decision,
        tool=action.normalized["tool"],
        operation=action.normalized["operation"],
    )

    return decision


async def _ensure_execution_context(
    db: AsyncSession, record: RuntimeActionModel, agent: AgentIdentity,
) -> None:
    """Re-check mutable scope state immediately before a runtime claims execution."""
    agent_record = (await db.execute(select(AgentModel).where(AgentModel.id == agent.id))).scalar_one_or_none()
    if not agent_record or agent_record.status == "suspended":
        raise HTTPException(status_code=403, detail="Agent is suspended; execution prohibited")
    if agent_record.status != "active":
        raise HTTPException(status_code=403, detail="Agent is inactive; execution prohibited")
    org_rec = (await db.execute(select(OrganizationModel).where(OrganizationModel.id == agent.organization_id))).scalar_one_or_none()
    if org_rec and org_rec.status == "suspended":
        raise HTTPException(status_code=403, detail="Organization is suspended; execution prohibited")
    proj_rec = (await db.execute(select(ProjectModel).where(ProjectModel.id == agent.project_id))).scalar_one_or_none()
    if proj_rec and proj_rec.status == "suspended":
        raise HTTPException(status_code=403, detail="Project is suspended; execution prohibited")
    await owned_session(db, record.session_id, agent)


async def _claim_execution_authorization(
    action_id: str, request: ExecuteActionRequest, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    """Atomically claim authorization before an external runtime side effect."""
    row = await db.execute(select(RuntimeActionModel).where(
        RuntimeActionModel.id == action_id, RuntimeActionModel.agent_id == agent.id,
        RuntimeActionModel.organization_id == agent.organization_id,
    ))
    record = row.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Action not found")

    action = stored_action(record)
    now = datetime.now(timezone.utc)
    await _ensure_execution_context(db, record, agent)

    if not gateway().verify_authorization(request.execution_authorization, action, identity_from(agent)):
        raise HTTPException(status_code=403, detail="Invalid, expired, or unusable execution authorization")

    token_hash = hashlib.sha256(request.execution_authorization.encode()).hexdigest()
    claim_stmt = (
        update(ExecutionAuthorizationModel)
        .where(
            ExecutionAuthorizationModel.action_id == action_id,
            ExecutionAuthorizationModel.token_hash == token_hash,
            ExecutionAuthorizationModel.state == "ISSUED",
            ExecutionAuthorizationModel.used_at.is_(None),
            ExecutionAuthorizationModel.expires_at > now,
        )
        .values(state="CLAIMED", claimed_at=now)
        .execution_options(synchronize_session=False)
    )
    claim_result = await db.execute(claim_stmt)
    if claim_result.rowcount == 0:
        raise HTTPException(status_code=409, detail="Execution authorization is not available to claim")
    record.execution_status = "EXECUTION_CLAIMED"
    await AuditService.record_event(
        db,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        session_id=record.session_id,
        action_id=action_id,
        tool_name=record.tool,
        canonical_action_hash=record.action_digest,
        policy_decision=record.decision,
        execution_state="EXECUTION_CLAIMED",
        severity="INFO",
        event_type="action.authorization_claimed",
        details={"authorization_state": "CLAIMED"},
    )
    await db.execute(
        update(AgentModel)
        .where(AgentModel.id == agent.id)
        .values(
            connection_status="connected",
            last_seen_at=datetime.now(timezone.utc),
            governed_requests_count=AgentModel.governed_requests_count + 1,
        )
    )
    await db.commit()
    await ws_manager.broadcast({
        "type": "ACTION_CLAIMED",
        "action_id": action_id,
        "agent_id": agent.id,
        "organization_id": agent.organization_id,
        "decision": record.decision,
        "execution_status": "EXECUTION_CLAIMED",
        "timestamp": datetime.now(timezone.utc),
    })
    return {"action_id": action_id, "status": "EXECUTION_CLAIMED", "claimed_at": now}


@router.post("/actions/{action_id}/claim")
async def claim_execution_authorization(
    action_id: str, request: ExecuteActionRequest, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    return await _claim_execution_authorization(action_id, request, db, agent)


@router.post("/actions/{action_id}/execute", deprecated=True)
async def execute_allowed_action(
    action_id: str, request: ExecuteActionRequest, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    """Compatibility alias for claim; real tool execution remains in the runtime."""
    return await _claim_execution_authorization(action_id, request, db, agent)


@router.post("/actions/{action_id}/result")
async def report_action_result(
    action_id: str, request: ReportResultRequest, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    row = await db.execute(select(RuntimeActionModel).where(RuntimeActionModel.id == action_id,
        RuntimeActionModel.agent_id == agent.id, RuntimeActionModel.organization_id == agent.organization_id))
    record = row.scalar_one_or_none()
    if not record or not gateway().verify_authorization(request.execution_authorization, stored_action(record), identity_from(agent)):
        raise HTTPException(status_code=403, detail="Result authorization is not bound to this action")

    now = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(request.execution_authorization.encode()).hexdigest()
    result_hash = canonical_result_hash(request.status, request.output)
    auth_row = await db.execute(select(ExecutionAuthorizationModel).where(
        ExecutionAuthorizationModel.action_id == action_id,
        ExecutionAuthorizationModel.token_hash == token_hash,
    ))
    authorization = auth_row.scalar_one_or_none()
    auth_exp = _to_utc(authorization.expires_at) if authorization else None
    if not authorization or not auth_exp or auth_exp <= now:
        raise HTTPException(status_code=403, detail="Invalid, expired, or unusable execution authorization")
    if authorization.state in {"SUCCEEDED", "FAILED"}:
        if authorization.result_hash == result_hash:
            return {"action_id": action_id, "status": authorization.state, "idempotent": True}
        raise HTTPException(status_code=409, detail="Conflicting duplicate execution result")
    if authorization.state != "CLAIMED":
        raise HTTPException(status_code=409, detail="Execution authorization must be claimed before reporting a result")
    claim_stmt = (
        update(ExecutionAuthorizationModel)
        .where(
            ExecutionAuthorizationModel.action_id == action_id,
            ExecutionAuthorizationModel.token_hash == token_hash,
            ExecutionAuthorizationModel.state == "CLAIMED",
            ExecutionAuthorizationModel.used_at.is_(None),
            ExecutionAuthorizationModel.expires_at > now,
        )
        .values(
            state="SUCCEEDED" if request.status == "succeeded" else "FAILED",
            completed_at=now,
            used_at=now,
            result_hash=result_hash,
            last_error=(redact_sensitive_data(str(request.output)) if request.status == "failed" else None),
        )
        .execution_options(synchronize_session=False)
    )
    claim_result = await db.execute(claim_stmt)
    if claim_result.rowcount == 0:
        raise HTTPException(status_code=403, detail="Invalid, expired, or already-used execution authorization")

    terminal_state = "SUCCEEDED" if request.status == "succeeded" else "FAILED"
    record.execution_status, record.result = terminal_state, request.output
    await db.execute(
        update(AgentModel)
        .where(AgentModel.id == agent.id)
        .values(
            connection_status="connected",
            last_seen_at=datetime.now(timezone.utc),
            governed_requests_count=AgentModel.governed_requests_count + 1,
        )
    )
    await db.commit()

    if request.output:
        output_wrapper = InjectionDetector.wrap_untrusted_output(request.output, source_tool=record.tool)
        if output_wrapper.threat_scan.threat_detected:
            await AnomalyMonitoringService.record_injection_threat(
                agent_id=agent.id,
                source_tool=record.tool,
                scan_result_dict={
                    "risk_score": output_wrapper.threat_scan.risk_score,
                    "categories": [c.value for c in output_wrapper.threat_scan.categories],
                    "matched_patterns": output_wrapper.threat_scan.matched_patterns,
                },
            )

    await ws_manager.broadcast({
        "type": "ACTION_RESULT",
        "action_id": action_id,
        "agent_id": agent.id,
        "organization_id": agent.organization_id,
        "decision": record.decision,
        "execution_status": record.execution_status,
        "timestamp": datetime.now(timezone.utc),
    })

    await AuditService.record_event(
        db,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        session_id=record.session_id,
        action_id=action_id,
        tool_name=record.tool,
        canonical_action_hash=record.action_digest,
        policy_decision=record.decision,
        execution_state=terminal_state,
        severity="ERROR" if terminal_state == "FAILED" else "INFO",
        event_type="action.failed" if terminal_state == "FAILED" else "action.executed",
        details={"output": request.output},
    )
    await db.commit()
    return {"action_id": action_id, "status": terminal_state, "idempotent": False}


@router.get("/activity", response_model=list[RuntimeActivity])
async def activity(
    limit: int = 100, db: AsyncSession = Depends(get_db), agent: AgentIdentity = Depends(authenticate_agent_async),
):
    rows = await db.execute(select(RuntimeActionModel).where(
        RuntimeActionModel.organization_id == agent.organization_id,
        RuntimeActionModel.agent_id == agent.id,
    ).order_by(RuntimeActionModel.created_at.desc()).limit(min(limit, 200)))
    return [RuntimeActivity(action_id=r.id, organization_id=r.organization_id, project_id=r.project_id,
        agent_id=r.agent_id, session_id=r.session_id, tool=r.tool, operation=r.operation, resource=r.resource,
        decision=r.decision, action_digest=r.action_digest, correlation_id=r.correlation_id, timestamp=r.created_at)
        for r in rows.scalars()]
@router.get("/approvals/{ticket_id}")
async def get_runtime_approval_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    ticket_row = await db.execute(
        select(ApprovalRequestModel).where(ApprovalRequestModel.ticket_id == ticket_id)
    )
    ticket = ticket_row.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Approval ticket not found")

    if ticket.action_id.startswith("llm_req_"):
        llm_row = await db.execute(
            select(LLMPendingRequestModel).where(LLMPendingRequestModel.id == ticket.action_id)
        )
        action = llm_row.scalar_one_or_none()
    else:
        action_row = await db.execute(
            select(RuntimeActionModel).where(RuntimeActionModel.id == ticket.action_id)
        )
        action = action_row.scalar_one_or_none()

    if not action or action.agent_id != agent.id or action.organization_id != agent.organization_id:
        raise HTTPException(status_code=404, detail="Approval ticket not found")

    response_data: dict[str, Any] = {"status": ticket.status}
    if ticket.status == "APPROVED" and ticket.execution_token:
        auth_row = await db.execute(
            select(ExecutionAuthorizationModel).where(ExecutionAuthorizationModel.action_id == action.id)
        )
        auth = auth_row.scalars().first()
        if not auth or (auth.used_at is None and auth.state == "ISSUED"):
            response_data["execution_authorization"] = ticket.execution_token

    return response_data
