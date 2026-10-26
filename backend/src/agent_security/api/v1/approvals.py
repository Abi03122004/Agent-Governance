"""HITL Approval Management API Endpoints."""

from datetime import datetime, timezone
import hashlib
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.config import get_settings
from agent_security.db.models import (
    AgentModel,
    ApprovalRequestModel,
    ExecutionAuthorizationModel,
    MembershipModel,
    OrganizationModel,
    ProjectModel,
    RuntimeActionModel,
)
from agent_security.db.session import get_db
from agent_security.domain.identity import User
from agent_security.middleware.auth import get_current_user
from agent_security.services.realtime import ws_manager
from agent_security.services.runtime_gateway import AuthenticatedAgent, RuntimeGateway, StoredAction
from agent_security.services.audit_service import AuditService

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ApprovalTicketResponse(BaseModel):
    ticket_id: str
    organization_id: str
    action_id: str
    canonical_action_hash: str
    status: str
    created_at: datetime
    expires_at: datetime
    decided_at: Optional[datetime] = None
    approver_id: Optional[str] = None
    reason: Optional[str] = None
    execution_authorization: Optional[str] = None
    execution_authorization_expires_at: Optional[datetime] = None


class ApprovalDecisionRequest(BaseModel):
    rationale: str = Field(..., min_length=1, max_length=512)


@router.get("", response_model=List[ApprovalTicketResponse])
async def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status"),
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(ApprovalRequestModel)
    if organization_id:
        mem_res = await db.execute(
            select(MembershipModel).where(
                MembershipModel.user_id == current_user.id,
                MembershipModel.organization_id == organization_id,
            )
        )
        if not mem_res.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="Forbidden: User is not authorized to access resources in this organization",
            )
        stmt = stmt.where(ApprovalRequestModel.organization_id == organization_id)
    else:
        mem_res = await db.execute(
            select(MembershipModel.organization_id).where(MembershipModel.user_id == current_user.id)
        )
        user_org_ids = [r[0] for r in mem_res.all()]
        if not user_org_ids:
            return []
        stmt = stmt.where(ApprovalRequestModel.organization_id.in_(user_org_ids))

    if status_filter:
        stmt = stmt.where(ApprovalRequestModel.status == status_filter.upper())
    res = await db.execute(stmt.order_by(ApprovalRequestModel.created_at.desc()))
    tickets = res.scalars().all()
    return [
        ApprovalTicketResponse(
            ticket_id=t.ticket_id,
            organization_id=t.organization_id,
            action_id=t.action_id,
            canonical_action_hash=t.canonical_action_hash,
            status=t.status,
            created_at=t.created_at,
            expires_at=t.expires_at,
            decided_at=t.decided_at,
            approver_id=t.approver_id,
            reason=t.reason,
        )
        for t in tickets
    ]


@router.get("/{ticket_id}", response_model=ApprovalTicketResponse)
async def get_approval(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(ApprovalRequestModel).where(ApprovalRequestModel.ticket_id == ticket_id))
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Approval ticket not found")

    mem_res = await db.execute(
        select(MembershipModel).where(
            MembershipModel.user_id == current_user.id,
            MembershipModel.organization_id == ticket.organization_id,
        )
    )
    if not mem_res.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail="Forbidden: User is not authorized to view approvals for this organization",
        )

    return ApprovalTicketResponse(
        ticket_id=ticket.ticket_id,
        organization_id=ticket.organization_id,
        action_id=ticket.action_id,
        canonical_action_hash=ticket.canonical_action_hash,
        status=ticket.status,
        created_at=ticket.created_at,
        expires_at=ticket.expires_at,
        decided_at=ticket.decided_at,
        approver_id=ticket.approver_id,
        reason=ticket.reason,
    )


@router.post("/{ticket_id}/approve", response_model=ApprovalTicketResponse)
async def approve_ticket(
    ticket_id: str,
    decision_req: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(ApprovalRequestModel).where(ApprovalRequestModel.ticket_id == ticket_id))
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Approval ticket not found")

    if ticket.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Ticket is already {ticket.status}")

    now = datetime.now(timezone.utc)
    exp = _to_utc(ticket.expires_at)
    if exp and exp < now:
        ticket.status = "EXPIRED"
        await db.commit()
        raise HTTPException(status_code=400, detail="Approval ticket has expired")

    # Verify approver role in organization
    mem_res = await db.execute(
        select(MembershipModel).where(
            MembershipModel.user_id == current_user.id,
            MembershipModel.organization_id == ticket.organization_id,
        )
    )
    membership = mem_res.scalar_one_or_none()
    if not membership or membership.role not in {"administrator", "security_operator", "approver"}:
        raise HTTPException(status_code=403, detail="User not authorized to approve actions for this organization")

    # Fetch associated runtime action
    act_res = await db.execute(select(RuntimeActionModel).where(RuntimeActionModel.id == ticket.action_id))
    action_record = act_res.scalar_one_or_none()
    if not action_record:
        raise HTTPException(status_code=404, detail="Bound action record not found")

    # Cryptographic binding check: action hash must match exactly
    if action_record.action_digest != ticket.canonical_action_hash:
        ticket.status = "REJECTED"
        ticket.reason = "Security violation: Action arguments tampered since approval request"
        await db.commit()
        raise HTTPException(status_code=409, detail="Action digest mismatch: action has been tampered with")

    # Fetch agent to verify requester/approver separation and suspension status
    agent_res = await db.execute(select(AgentModel).where(AgentModel.id == action_record.agent_id))
    agent = agent_res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Requester / Approver separation: agent owner cannot approve their own agent's action
    if agent.owner == current_user.email:
        raise HTTPException(status_code=403, detail="Requester and approver separation required: agent owner cannot approve")

    # Check suspension status of agent, project, organization
    if agent.status == "suspended":
        raise HTTPException(status_code=403, detail="Agent is suspended; approval prohibited")

    org_res = await db.execute(select(OrganizationModel).where(OrganizationModel.id == agent.organization_id))
    org = org_res.scalar_one_or_none()
    if org and org.status == "suspended":
        raise HTTPException(status_code=403, detail="Organization is suspended; approval prohibited")

    proj_res = await db.execute(select(ProjectModel).where(ProjectModel.id == agent.project_id))
    proj = proj_res.scalar_one_or_none()
    if proj and proj.status == "suspended":
        raise HTTPException(status_code=403, detail="Project is suspended; approval prohibited")

    # Issue execution authorization
    settings = get_settings()
    gateway = RuntimeGateway(settings.SECRET_KEY, settings.EXECUTION_AUTH_TTL_SECONDS)
    stored = StoredAction(
        action_id=action_record.id,
        identity=AuthenticatedAgent(agent.organization_id, agent.project_id, agent.id, agent.status),
        session_id=action_record.session_id,
        normalized=action_record.normalized_action,
        digest=action_record.action_digest,
        decision="ALLOW",
        correlation_id=action_record.correlation_id,
        created_at=action_record.created_at,
    )
    token, token_expires_at = gateway.issue_authorization(stored)

    # Persist authorization model
    auth_model = ExecutionAuthorizationModel(
        id="auth_" + uuid.uuid4().hex,
        action_id=action_record.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=token_expires_at,
    )
    db.add(auth_model)

    ticket.status = "APPROVED"
    ticket.approver_id = current_user.id
    ticket.reason = decision_req.rationale
    ticket.decided_at = now

    action_record.decision = "ALLOW"
    action_record.execution_status = "APPROVED"

    await AuditService.record_event(
        db,
        organization_id=ticket.organization_id,
        project_id=action_record.project_id,
        agent_id=action_record.agent_id,
        session_id=action_record.session_id,
        action_id=action_record.id,
        tool_name=action_record.tool,
        canonical_action_hash=action_record.action_digest,
        policy_decision="ALLOW",
        execution_state="APPROVED",
        severity="INFO",
        event_type="approval.approved",
        details={"ticket_id": ticket.ticket_id, "approver_id": current_user.id, "rationale": decision_req.rationale},
    )
    await db.commit()

    await ws_manager.broadcast({
        "type": "ACTION_APPROVED",
        "ticket_id": ticket.ticket_id,
        "action_id": ticket.action_id,
        "organization_id": ticket.organization_id,
        "approver_id": current_user.id,
        "rationale": decision_req.rationale,
        "timestamp": now,
    })

    return ApprovalTicketResponse(
        ticket_id=ticket.ticket_id,
        organization_id=ticket.organization_id,
        action_id=ticket.action_id,
        canonical_action_hash=ticket.canonical_action_hash,
        status=ticket.status,
        created_at=ticket.created_at,
        expires_at=ticket.expires_at,
        decided_at=ticket.decided_at,
        approver_id=ticket.approver_id,
        reason=ticket.reason,
        execution_authorization=token,
        execution_authorization_expires_at=token_expires_at,
    )


@router.post("/{ticket_id}/reject", response_model=ApprovalTicketResponse)
async def reject_ticket(
    ticket_id: str,
    decision_req: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(ApprovalRequestModel).where(ApprovalRequestModel.ticket_id == ticket_id))
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Approval ticket not found")

    if ticket.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Ticket is already {ticket.status}")

    # Verify approver role in organization
    mem_res = await db.execute(
        select(MembershipModel).where(
            MembershipModel.user_id == current_user.id,
            MembershipModel.organization_id == ticket.organization_id,
        )
    )
    membership = mem_res.scalar_one_or_none()
    if not membership or membership.role not in {"administrator", "security_operator", "approver"}:
        raise HTTPException(status_code=403, detail="User not authorized to reject actions for this organization")

    now = datetime.now(timezone.utc)
    ticket.status = "REJECTED"
    ticket.approver_id = current_user.id
    ticket.reason = decision_req.rationale
    ticket.decided_at = now

    act_res = await db.execute(select(RuntimeActionModel).where(RuntimeActionModel.id == ticket.action_id))
    action_record = act_res.scalar_one_or_none()
    if action_record:
        action_record.execution_status = "REJECTED"
        await AuditService.record_event(
            db,
            organization_id=ticket.organization_id,
            project_id=action_record.project_id,
            agent_id=action_record.agent_id,
            session_id=action_record.session_id,
            action_id=action_record.id,
            tool_name=action_record.tool,
            canonical_action_hash=action_record.action_digest,
            policy_decision="REJECTED",
            execution_state="REJECTED",
            severity="WARN",
            event_type="approval.rejected",
            details={"ticket_id": ticket.ticket_id, "approver_id": current_user.id, "rationale": decision_req.rationale},
        )

    await db.commit()

    await ws_manager.broadcast({
        "type": "ACTION_REJECTED",
        "ticket_id": ticket.ticket_id,
        "action_id": ticket.action_id,
        "organization_id": ticket.organization_id,
        "approver_id": current_user.id,
        "rationale": decision_req.rationale,
        "timestamp": now,
    })

    return ApprovalTicketResponse(
        ticket_id=ticket.ticket_id,
        organization_id=ticket.organization_id,
        action_id=ticket.action_id,
        canonical_action_hash=ticket.canonical_action_hash,
        status=ticket.status,
        created_at=ticket.created_at,
        expires_at=ticket.expires_at,
        decided_at=ticket.decided_at,
        approver_id=ticket.approver_id,
        reason=ticket.reason,
    )
