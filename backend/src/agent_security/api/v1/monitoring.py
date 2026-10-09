"""Human control-plane views of runtime activity, stats, and realtime WebSocket updates."""

from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect

from agent_security.db.models import AgentModel, AgentSessionModel, MembershipModel, RuntimeActionModel, UserModel
from agent_security.db.session import get_db
from agent_security.services.realtime import ws_manager

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/stats")
async def monitoring_stats(
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve high-level governance and enforcement metrics for the dashboard."""
    # Active agents count
    agent_stmt = select(func.count(AgentModel.id)).where(AgentModel.status == "active")
    if organization_id:
        agent_stmt = agent_stmt.where(AgentModel.organization_id == organization_id)
    active_agents = (await db.execute(agent_stmt)).scalar() or 0

    # Suspended agents count
    sus_agent_stmt = select(func.count(AgentModel.id)).where(AgentModel.status == "suspended")
    if organization_id:
        sus_agent_stmt = sus_agent_stmt.where(AgentModel.organization_id == organization_id)
    suspended_agents = (await db.execute(sus_agent_stmt)).scalar() or 0

    # Action counts by decision
    action_stmt = select(RuntimeActionModel.decision, func.count(RuntimeActionModel.id))
    if organization_id:
        action_stmt = action_stmt.where(RuntimeActionModel.organization_id == organization_id)
    action_stmt = action_stmt.group_by(RuntimeActionModel.decision)
    rows = (await db.execute(action_stmt)).all()
    decision_counts = {r[0]: r[1] for r in rows}

    allowed = decision_counts.get("ALLOW", 0)
    blocked = decision_counts.get("BLOCK", 0)
    require_approval = decision_counts.get("REQUIRE_APPROVAL", 0)
    suspended_actions = decision_counts.get("SUSPEND", 0)
    total_actions = sum(decision_counts.values())

    return {
        "active_agents": active_agents,
        "suspended_agents": suspended_agents,
        "actions_today": total_actions,
        "total_actions": total_actions,
        "allowed": allowed,
        "blocked": blocked,
        "pending_approval": require_approval,
        "suspended": suspended_actions + suspended_agents,
    }


@router.get("/agents")
async def monitored_agents(
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List agents with activity telemetry."""
    statement = select(
        AgentModel.id,
        AgentModel.name,
        AgentModel.organization_id,
        AgentModel.project_id,
        AgentModel.environment,
        AgentModel.status,
        func.max(RuntimeActionModel.created_at).label("last_activity"),
        func.count(RuntimeActionModel.id).label("action_count"),
    ).outerjoin(RuntimeActionModel, RuntimeActionModel.agent_id == AgentModel.id)

    if organization_id:
        statement = statement.where(AgentModel.organization_id == organization_id)

    statement = statement.group_by(
        AgentModel.id,
        AgentModel.name,
        AgentModel.organization_id,
        AgentModel.project_id,
        AgentModel.environment,
        AgentModel.status,
    )
    rows = (await db.execute(statement)).all()
    return [
        {
            "agent_id": r.id,
            "name": r.name,
            "organization_id": r.organization_id,
            "project_id": r.project_id,
            "environment": r.environment,
            "status": r.status,
            "last_activity": r.last_activity,
            "action_count": r.action_count,
        }
        for r in rows
    ]


@router.get("/agents/{agent_id}")
async def agent_detail(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve deep detail for an agent including its sessions and recent actions."""
    agent_row = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = agent_row.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    sessions_row = await db.execute(
        select(AgentSessionModel)
        .where(AgentSessionModel.agent_id == agent_id)
        .order_by(AgentSessionModel.started_at.desc())
        .limit(20)
    )
    sessions = sessions_row.scalars().all()

    actions_row = await db.execute(
        select(RuntimeActionModel)
        .where(RuntimeActionModel.agent_id == agent_id)
        .order_by(RuntimeActionModel.created_at.desc())
        .limit(50)
    )
    actions = actions_row.scalars().all()

    return {
        "agent": {
            "id": agent.id,
            "organization_id": agent.organization_id,
            "project_id": agent.project_id,
            "name": agent.name,
            "owner": agent.owner,
            "environment": agent.environment,
            "purpose": agent.purpose,
            "status": agent.status,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        },
        "sessions": [
            {
                "session_id": s.session_id,
                "status": s.status,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
            }
            for s in sessions
        ],
        "recent_actions": [
            {
                "action_id": a.id,
                "session_id": a.session_id,
                "tool": a.tool,
                "operation": a.operation,
                "resource": a.resource,
                "decision": a.decision,
                "execution_status": a.execution_status,
                "action_digest": a.action_digest,
                "correlation_id": a.correlation_id,
                "timestamp": a.created_at,
            }
            for a in actions
        ],
    }


@router.get("/activity")
async def runtime_activity(
    organization_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Fetch live or paginated runtime activity events."""
    stmt = select(RuntimeActionModel)
    if organization_id:
        stmt = stmt.where(RuntimeActionModel.organization_id == organization_id)
    if agent_id:
        stmt = stmt.where(RuntimeActionModel.agent_id == agent_id)

    stmt = stmt.order_by(RuntimeActionModel.created_at.desc()).limit(min(limit, 500))
    rows = await db.execute(stmt)
    return [
        {
            "action_id": r.id,
            "organization_id": r.organization_id,
            "project_id": r.project_id,
            "agent_id": r.agent_id,
            "session_id": r.session_id,
            "tool": r.tool,
            "operation": r.operation,
            "resource": r.resource,
            "decision": r.decision,
            "reason_code": r.reason_code,
            "execution_status": r.execution_status,
            "action_digest": r.action_digest,
            "correlation_id": r.correlation_id,
            "timestamp": r.created_at,
        }
        for r in rows.scalars()
    ]


@router.get("/policies")
async def list_policies():
    """List deterministic security policies enforced by the platform."""
    return [
        {
            "id": "pol_agent_suspension",
            "name": "Agent Suspension Enforcement",
            "decision": "SUSPEND",
            "condition": "identity.status == 'suspended'",
            "description": "Immediately halts any action from an agent flagged as suspended or revoked by an administrator or kill switch.",
            "priority": 1,
            "status": "active",
        },
        {
            "id": "pol_destructive_block",
            "name": "Destructive Operations Block",
            "decision": "BLOCK",
            "condition": "operation in ['delete', 'drop', 'destroy']",
            "description": "Completely forbids unapproved destructive side-effects on platform or tenant databases.",
            "priority": 2,
            "status": "active",
        },
        {
            "id": "pol_external_egress",
            "name": "External Network Egress Guard",
            "decision": "BLOCK",
            "condition": "tool in ['external', 'http'] and operation in ['send', 'post', 'write']",
            "description": "Restricts external outbound calls to prevent data exfiltration.",
            "priority": 3,
            "status": "active",
        },
        {
            "id": "pol_secrets_protection",
            "name": "Restricted Resources & Secrets Sandbox",
            "decision": "BLOCK",
            "condition": "resource starts with ('secrets', 'credentials', 'forbidden')",
            "description": "Blocks agent access to restricted resource scopes and system credentials.",
            "priority": 4,
            "status": "active",
        },
        {
            "id": "pol_mutation_approval",
            "name": "Production Mutation Approval Required",
            "decision": "REQUIRE_APPROVAL",
            "condition": "operation in ['write', 'update'] and tool != 'safe_echo'",
            "description": "Requires human approver cryptographic sign-off before committing state changes.",
            "priority": 5,
            "status": "active",
        },
        {
            "id": "pol_allow_permitted",
            "name": "Deterministic Allowed Operations",
            "decision": "ALLOW",
            "condition": "authorized + permitted in contract",
            "description": "Permits safe read operations and validated tool execution with a single-use authorization token.",
            "priority": 100,
            "status": "active",
        },
    ]


@router.websocket("/ws/activity")
async def websocket_activity(websocket: WebSocket):
    """Realtime stream of action evaluations and executions for the Dashboard."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive receive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
