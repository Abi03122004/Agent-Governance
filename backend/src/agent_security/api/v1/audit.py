"""Audit Events Query and Integrity Verification API."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.runtime_activity import AuditEventModel
from agent_security.db.session import get_db
from agent_security.domain.identity import User
from agent_security.middleware.auth import (
    get_current_user,
    get_user_authorized_org_ids,
    verify_user_org_membership,
)
from agent_security.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit"])


class ClearAuditRequest(BaseModel):
    confirmation: str = Field(..., description="Must be 'CONFIRM'")
    rationale: Optional[str] = Field("Human Operator audit ledger re-initialization")


@router.delete("/events")
@router.post("/clear")
async def clear_audit_events(
    payload: Optional[ClearAuditRequest] = None,
    organization_id: Optional[str] = Query(None),
    confirmation: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purge audit ledger logs and re-initialize cryptographic chain. Only accessible by authenticated human operator."""
    conf = (payload.confirmation if payload else None) or confirmation
    if conf != "CONFIRM":
        raise HTTPException(
            status_code=400,
            detail="Human operator confirmation required. Must provide confirmation='CONFIRM'",
        )

    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        target_org_ids = [organization_id]
    else:
        target_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not target_org_ids:
            raise HTTPException(status_code=403, detail="Forbidden: User is not authorized for any organization")

    del_stmt = delete(AuditEventModel).where(AuditEventModel.organization_id.in_(target_org_ids))
    res = await db.execute(del_stmt)
    deleted_count = res.rowcount or 0
    await db.flush()

    rationale = (payload.rationale if payload else None) or "Human operator ledger reset"
    for org_id in target_org_ids:
        await AuditService.record_event(
            db,
            organization_id=org_id,
            event_type="audit.ledger_cleared_by_human",
            severity="WARN",
            details={
                "operator": current_user.email or current_user.id,
                "rationale": rationale,
                "previous_events_purged": deleted_count,
            },
        )

    await db.commit()
    return {
        "status": "cleared",
        "purged_count": deleted_count,
        "organizations": target_org_ids,
        "message": f"Successfully purged {deleted_count} audit event records and reinitialized cryptographic ledger.",
    }



@router.get("/events")
async def list_audit_events(
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve immutable, tenant-scoped audit records with query filters."""
    query = select(AuditEventModel)

    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        query = query.where(AuditEventModel.organization_id == organization_id)
    else:
        user_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not user_org_ids:
            return []
        query = query.where(AuditEventModel.organization_id.in_(user_org_ids))

    if agent_id:
        query = query.where(AuditEventModel.agent_id == agent_id)
    if session_id:
        query = query.where(AuditEventModel.session_id == session_id)
    if event_type:
        query = query.where(AuditEventModel.event_type == event_type)
    if severity:
        query = query.where(AuditEventModel.severity == severity)

    query = query.order_by(AuditEventModel.timestamp.desc(), AuditEventModel.event_id.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        {
            "event_id": e.event_id,
            "organization_id": e.organization_id,
            "project_id": e.project_id,
            "agent_id": e.agent_id,
            "session_id": e.session_id,
            "task_id": e.task_id,
            "action_id": e.action_id,
            "tool_name": e.tool_name,
            "canonical_action_hash": e.canonical_action_hash,
            "policy_decision": e.policy_decision,
            "execution_state": e.execution_state,
            "severity": e.severity,
            "event_type": e.event_type,
            "details": e.details,
            "previous_event_hash": e.previous_event_hash,
            "event_hash": e.event_hash,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]


@router.get("/verify-chain")
async def verify_audit_chain(
    organization_id: Optional[str] = Query(None, description="Organization ID to verify audit log integrity"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cryptographically verify the hash chain integrity for an organization's audit log."""
    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        org_id = organization_id
    else:
        user_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not user_org_ids:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: User is not authorized for any organization",
            )
        if len(user_org_ids) == 1:
            org_id = user_org_ids[0]
        else:
            raise HTTPException(
                status_code=400,
                detail="organization_id query parameter is required when user belongs to multiple organizations",
            )

    is_valid, verified_count, error = await AuditService.verify_chain(db, org_id)
    return {
        "organization_id": org_id,
        "valid": is_valid,
        "verified": is_valid,
        "verified_count": verified_count,
        "event_count": verified_count,
        "error": error,
        "message": error if error else f"All {verified_count} audit events cryptographically verified.",
    }

