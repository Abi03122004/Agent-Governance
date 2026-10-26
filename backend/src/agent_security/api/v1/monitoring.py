"""Human control-plane views of runtime activity, stats, and realtime WebSocket updates."""

from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status, Query

from agent_security.config import get_settings
from agent_security.db.models import (
    AgentModel,
    AgentSessionModel,
    MembershipModel,
    RuntimeActionModel,
    UserModel,
    ApprovalRequestModel,
    ExecutionAuthorizationModel,
    OrganizationModel,
)
from agent_security.services.audit_service import AuditService
from agent_security.db.session import get_db, get_session_maker
from agent_security.domain.identity import User
from agent_security.middleware.auth import (
    get_current_user,
    get_user_authorized_org_ids,
    verify_user_org_membership,
)
from agent_security.security.authentication import verify_user_token
from agent_security.services.realtime import ws_manager

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/stats")
async def monitoring_stats(
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve high-level governance and enforcement metrics for the dashboard."""
    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        target_org_ids = [organization_id]
    else:
        target_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not target_org_ids:
            return {
                "active_agents": 0,
                "suspended_agents": 0,
                "actions_today": 0,
                "total_actions": 0,
                "allowed": 0,
                "blocked": 0,
                "pending_approval": 0,
                "suspended": 0,
            }

    # Active agents count scoped to authorized organizations
    agent_stmt = (
        select(func.count(AgentModel.id))
        .where(AgentModel.status == "active")
        .where(AgentModel.organization_id.in_(target_org_ids))
    )
    active_agents = (await db.execute(agent_stmt)).scalar() or 0

    # Suspended agents count scoped to authorized organizations
    sus_agent_stmt = (
        select(func.count(AgentModel.id))
        .where(AgentModel.status == "suspended")
        .where(AgentModel.organization_id.in_(target_org_ids))
    )
    suspended_agents = (await db.execute(sus_agent_stmt)).scalar() or 0

    # Action counts by decision scoped to authorized organizations
    action_stmt = (
        select(RuntimeActionModel.decision, func.count(RuntimeActionModel.id))
        .where(RuntimeActionModel.organization_id.in_(target_org_ids))
        .group_by(RuntimeActionModel.decision)
    )
    rows = (await db.execute(action_stmt)).all()
    decision_counts = {r[0]: r[1] for r in rows}

    allowed = decision_counts.get("ALLOW", 0)
    blocked = decision_counts.get("BLOCK", 0)
    suspended_actions = decision_counts.get("SUSPEND", 0)
    total_actions = sum(decision_counts.values())

    # Pending approvals: count actual pending tickets awaiting human reviewer action
    pending_appr_stmt = (
        select(func.count(ApprovalRequestModel.ticket_id))
        .where(ApprovalRequestModel.status == "PENDING")
        .where(ApprovalRequestModel.organization_id.in_(target_org_ids))
    )
    pending_approvals = (await db.execute(pending_appr_stmt)).scalar() or 0

    return {
        "active_agents": active_agents,
        "suspended_agents": suspended_agents,
        "actions_today": total_actions,
        "total_actions": total_actions,
        "allowed": allowed,
        "blocked": blocked,
        "pending_approval": pending_approvals,
        "suspended": suspended_actions + suspended_agents,
    }


@router.get("/agents")
async def monitored_agents(
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List agents with activity telemetry strictly within authorized tenant scope."""
    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        target_org_ids = [organization_id]
    else:
        target_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not target_org_ids:
            return []

    statement = (
        select(
            AgentModel.id,
            AgentModel.name,
            AgentModel.organization_id,
            AgentModel.project_id,
            AgentModel.environment,
            AgentModel.status,
            func.max(RuntimeActionModel.created_at).label("last_activity"),
            func.count(RuntimeActionModel.id).label("action_count"),
        )
        .outerjoin(RuntimeActionModel, RuntimeActionModel.agent_id == AgentModel.id)
        .where(AgentModel.organization_id.in_(target_org_ids))
        .group_by(
            AgentModel.id,
            AgentModel.name,
            AgentModel.organization_id,
            AgentModel.project_id,
            AgentModel.environment,
            AgentModel.status,
        )
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
    current_user: User = Depends(get_current_user),
):
    """Retrieve deep detail for an agent including its sessions and recent actions."""
    agent_row = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = agent_row.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await verify_user_org_membership(db, current_user.id, agent.organization_id)

    sessions_row = await db.execute(
        select(AgentSessionModel)
        .where(
            AgentSessionModel.agent_id == agent_id,
            AgentSessionModel.organization_id == agent.organization_id,
        )
        .order_by(AgentSessionModel.started_at.desc())
        .limit(20)
    )
    sessions = sessions_row.scalars().all()

    actions_row = await db.execute(
        select(RuntimeActionModel)
        .where(
            RuntimeActionModel.agent_id == agent_id,
            RuntimeActionModel.organization_id == agent.organization_id,
        )
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
    current_user: User = Depends(get_current_user),
):
    """Fetch live or paginated runtime activity events within authorized tenant scope."""
    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        target_org_ids = [organization_id]
    else:
        target_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not target_org_ids:
            return []

    stmt = select(RuntimeActionModel).where(RuntimeActionModel.organization_id.in_(target_org_ids))
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


class ClearHistoryRequest(BaseModel):
    confirmation: str = Field(..., description="Must be 'CONFIRM'")
    rationale: Optional[str] = Field("Human operator activity log purge")
    action_ids: Optional[list[str]] = Field(None, description="Specific action IDs to delete")


@router.delete("/activity")
@router.post("/activity/clear")
async def clear_runtime_activity(
    payload: Optional[ClearHistoryRequest] = None,
    organization_id: Optional[str] = Query(None),
    confirmation: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purge runtime action history and pending approvals. Only accessible by authenticated human operator."""
    conf = (payload.confirmation if payload else None) or confirmation
    if conf != "CONFIRM":
        raise HTTPException(
            status_code=400,
            detail="Human operator confirmation required. Must provide confirmation='CONFIRM'",
        )

    # 1. Selective deletion of specific actions
    if payload and payload.action_ids:
        action_ids = payload.action_ids
        del_auths = delete(ExecutionAuthorizationModel).where(ExecutionAuthorizationModel.action_id.in_(action_ids))
        del_actions = delete(RuntimeActionModel).where(RuntimeActionModel.id.in_(action_ids))
        del_approvals = delete(ApprovalRequestModel).where(ApprovalRequestModel.action_id.in_(action_ids))

        await db.execute(del_auths)
        await db.execute(del_approvals)
        res_act = await db.execute(del_actions)
        purged_count = res_act.rowcount or 0
        await db.commit()
        return {
            "status": "cleared",
            "purged_count": purged_count,
            "message": f"Successfully deleted {purged_count} selected runtime actions.",
        }

    # 2. Bulk clear history
    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        target_org_ids = [organization_id]
    else:
        target_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not target_org_ids:
            all_orgs = await db.execute(select(OrganizationModel.id))
            target_org_ids = [r[0] for r in all_orgs.all()]

    if not target_org_ids:
        del_auths = delete(ExecutionAuthorizationModel)
        del_actions = delete(RuntimeActionModel)
        del_approvals = delete(ApprovalRequestModel)
        await db.execute(del_auths)
        await db.execute(del_approvals)
        res_act = await db.execute(del_actions)
        purged_count = res_act.rowcount or 0
        await db.commit()
        return {
            "status": "cleared",
            "purged_count": purged_count,
            "message": f"Successfully cleared {purged_count} runtime actions from activity history.",
        }

    subq = select(RuntimeActionModel.id).where(RuntimeActionModel.organization_id.in_(target_org_ids))
    del_auths = delete(ExecutionAuthorizationModel).where(ExecutionAuthorizationModel.action_id.in_(subq))
    del_actions = delete(RuntimeActionModel).where(RuntimeActionModel.organization_id.in_(target_org_ids))
    del_approvals = delete(ApprovalRequestModel).where(ApprovalRequestModel.organization_id.in_(target_org_ids))

    await db.execute(del_auths)
    await db.execute(del_approvals)
    res_act = await db.execute(del_actions)
    purged_count = res_act.rowcount or 0

    rationale = (payload.rationale if payload else None) or "Human operator activity purge"
    for org_id in target_org_ids:
        await AuditService.record_event(
            db,
            organization_id=org_id,
            event_type="activity.history_cleared_by_human",
            severity="WARN",
            details={
                "operator": current_user.email or current_user.id,
                "purged_count": purged_count,
                "rationale": rationale,
            },
        )

    await db.commit()
    return {
        "status": "cleared",
        "purged_count": purged_count,
        "message": f"Successfully cleared {purged_count} runtime actions from activity history.",
    }


@router.get("/policies")
async def list_policies(current_user: User = Depends(get_current_user)):
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
async def websocket_activity(
    websocket: WebSocket,
    organization_id: Optional[str] = None,
    token: Optional[str] = None,
    user_email: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Realtime stream of action evaluations and executions scoped strictly to authorized tenant."""
    settings = get_settings()

    # 1. Resolve authentication credentials (Bearer JWT or explicit dev auth)
    auth_token = token or websocket.query_params.get("token")
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()

    resolved_user = None
    if auth_token:
        payload = verify_user_token(auth_token)
        if payload:
            sub = payload.get("sub")
            email = payload.get("email")
            res = await db.execute(
                select(UserModel).where(
                    (UserModel.id == sub) | (UserModel.email == email),
                    UserModel.status == "active",
                )
            )
            resolved_user = res.scalar_one_or_none()

    if not resolved_user and settings.ENVIRONMENT != "production" and settings.ALLOW_DEV_HEADER_AUTH:
        dev_email = user_email or websocket.query_params.get("user_email") or websocket.headers.get("x-user-email")
        if dev_email:
            res = await db.execute(
                select(UserModel).where(UserModel.email == dev_email, UserModel.status == "active")
            )
            resolved_user = res.scalar_one_or_none()

    if not resolved_user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return

    # 2. Enforce organization authorization
    req_org = (
        organization_id
        or websocket.query_params.get("organization_id")
        or websocket.headers.get("x-organization-id")
    )
    user_org_ids = await get_user_authorized_org_ids(db, resolved_user.id)
    if not user_org_ids:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User has no authorized organizations")
        return

    if req_org:
        if req_org not in user_org_ids:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized organization")
            return
        target_org = req_org
    else:
        target_org = user_org_ids[0]

    # 3. Connect to connection manager with organization scope
    await ws_manager.connect(websocket, organization_id=target_org)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

