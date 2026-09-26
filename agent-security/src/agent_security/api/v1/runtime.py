"""Provider-neutral, pre-side-effect runtime gateway endpoints."""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.config import get_settings
from agent_security.db.models import AgentSessionModel, ExecutionAuthorizationModel, RuntimeActionModel
from agent_security.db.session import get_db
from agent_security.domain.identity import AgentIdentity
from agent_security.domain.runtime import ExecuteActionRequest, ReportResultRequest, RuntimeActionInput, RuntimeActivity, RuntimeDecision
from agent_security.middleware.auth import authenticate_agent_async
from agent_security.services.runtime_gateway import AuthenticatedAgent, RuntimeGateway, StoredAction
from agent_security.services.realtime import ws_manager

router = APIRouter(prefix="/runtime", tags=["Runtime"])


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
    return session


def stored_action(row: RuntimeActionModel) -> StoredAction:
    identity = AuthenticatedAgent(row.organization_id, row.project_id, row.agent_id, "active")
    return StoredAction(row.id, identity, row.session_id, row.normalized_action, row.action_digest,
                        row.decision, row.correlation_id, row.created_at)


@router.post("/sessions", status_code=status.HTTP_201_CREATED, tags=["Runtime"])
async def start_runtime_session(
    db: AsyncSession = Depends(get_db), agent: AgentIdentity = Depends(authenticate_agent_async),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    session = AgentSessionModel(
        session_id="sess_" + uuid.uuid4().hex, organization_id=agent.organization_id,
        project_id=agent.project_id, agent_id=agent.id, status="active", correlation_id=correlation_id,
    )
    db.add(session)
    await db.commit()
    return {"session_id": session.session_id, "organization_id": agent.organization_id,
            "project_id": agent.project_id, "agent_id": agent.id, "status": "active"}


@router.post("/actions/evaluate", response_model=RuntimeDecision)
async def evaluate_action(
    request: RuntimeActionInput, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
):
    await owned_session(db, request.session_id, agent)
    correlation_id = correlation_id or "req_" + uuid.uuid4().hex
    service = gateway()
    action, decision = service.evaluate(identity_from(agent), request, correlation_id)
    
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
    if decision.execution_authorization and decision.execution_authorization_expires_at:
        db.add(ExecutionAuthorizationModel(
            id="auth_" + uuid.uuid4().hex, action_id=action.action_id,
            token_hash=hashlib.sha256(decision.execution_authorization.encode()).hexdigest(),
            expires_at=decision.execution_authorization_expires_at,
        ))
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

    return decision


@router.post("/actions/{action_id}/execute")
async def execute_allowed_action(
    action_id: str, request: ExecuteActionRequest, db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent_async),
):
    row = await db.execute(select(RuntimeActionModel).where(
        RuntimeActionModel.id == action_id, RuntimeActionModel.agent_id == agent.id,
        RuntimeActionModel.organization_id == agent.organization_id,
    ))
    record = row.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Action not found")
    authorization = (await db.execute(select(ExecutionAuthorizationModel).where(
        ExecutionAuthorizationModel.action_id == action_id,
        ExecutionAuthorizationModel.token_hash == hashlib.sha256(request.execution_authorization.encode()).hexdigest(),
    ))).scalar_one_or_none()
    action = stored_action(record)
    if (not authorization or authorization.used_at or authorization.expires_at < datetime.now(timezone.utc)
            or not gateway().verify_authorization(request.execution_authorization, action, identity_from(agent))):
        raise HTTPException(status_code=403, detail="Invalid, expired, or already-used execution authorization")
    # Mark used before invoking the protected tool: a retry cannot replay the authorization.
    authorization.used_at = datetime.now(timezone.utc)
    try:
        result = gateway().execute_safe_echo(action)
    except ValueError as exc:
        record.execution_status = "BLOCKED"
        await db.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record.execution_status, record.result = "EXECUTED", result
    await db.commit()

    await ws_manager.broadcast({
        "type": "ACTION_EXECUTED",
        "action_id": action_id,
        "agent_id": agent.id,
        "decision": record.decision,
        "execution_status": "EXECUTED",
        "timestamp": datetime.now(timezone.utc),
    })

    return {"action_id": action_id, "status": "EXECUTED", "result": result}


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
    record.execution_status, record.result = request.status.upper(), request.output
    await db.commit()

    await ws_manager.broadcast({
        "type": "ACTION_RESULT",
        "action_id": action_id,
        "agent_id": agent.id,
        "decision": record.decision,
        "execution_status": record.execution_status,
        "timestamp": datetime.now(timezone.utc),
    })

    return {"action_id": action_id, "status": record.execution_status}


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
