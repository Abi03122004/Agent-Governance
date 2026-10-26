"""Agent Sessions API Endpoints."""

import uuid
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import AgentSessionModel
from agent_security.domain.identity import AgentSession, AgentIdentity, User
from agent_security.middleware.auth import (
    authenticate_agent,
    get_current_user,
    get_user_authorized_org_ids,
    verify_user_org_membership,
)
from agent_security.services.audit_service import AuditService

router = APIRouter(prefix="/sessions", tags=["Sessions"])

class SessionCreateResponse(BaseModel):
    session_id: str
    organization_id: str
    project_id: str
    agent_id: str
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None

@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    correlation_id: Optional[str] = None, 
    expires_in_seconds: Optional[int] = None,
    db: AsyncSession = Depends(get_db), 
    agent: AgentIdentity = Depends(authenticate_agent)
):
    if agent.status == "suspended":
        raise HTTPException(status_code=403, detail="Suspended agent cannot start runtime session")
    if agent.status != "active":
        raise HTTPException(status_code=403, detail="Inactive agent cannot start runtime session")

    session_id = f"sess_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=expires_in_seconds)) if expires_in_seconds else None
    
    db_session = AgentSessionModel(
        session_id=session_id,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        status="active",
        correlation_id=correlation_id,
        expires_at=expires_at,
    )
    db.add(db_session)
    await db.flush()
    await AuditService.record_event(
        db,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        session_id=db_session.session_id,
        event_type="session.started",
        details={"expires_at": str(expires_at)},
    )
    await db.commit()
    await db.refresh(db_session)
    
    return SessionCreateResponse(
        session_id=db_session.session_id,
        organization_id=db_session.organization_id,
        project_id=db_session.project_id,
        agent_id=db_session.agent_id,
        status=db_session.status,
        started_at=db_session.started_at,
        expires_at=db_session.expires_at,
    )

@router.get("", response_model=List[SessionCreateResponse])
async def list_sessions(
    organization_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AgentSessionModel)
    if organization_id:
        await verify_user_org_membership(db, current_user.id, organization_id)
        stmt = stmt.where(AgentSessionModel.organization_id == organization_id)
    else:
        user_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not user_org_ids:
            return []
        stmt = stmt.where(AgentSessionModel.organization_id.in_(user_org_ids))

    if agent_id:
        stmt = stmt.where(AgentSessionModel.agent_id == agent_id)
    result = await db.execute(stmt.order_by(AgentSessionModel.started_at.desc()))
    rows = result.scalars().all()
    return [
        SessionCreateResponse(
            session_id=s.session_id,
            organization_id=s.organization_id,
            project_id=s.project_id,
            agent_id=s.agent_id,
            status=s.status,
            started_at=s.started_at,
        )
        for s in rows
    ]

@router.patch("/{session_id}/terminate", response_model=SessionCreateResponse)
async def terminate_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    agent: AgentIdentity = Depends(authenticate_agent)
):
    result = await db.execute(
        select(AgentSessionModel).where(
            AgentSessionModel.session_id == session_id,
            AgentSessionModel.agent_id == agent.id,
            AgentSessionModel.organization_id == agent.organization_id,
        )
    )
    db_session = result.scalar_one_or_none()
    
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found or not owned by agent")
        
    db_session.status = "terminated"
    db_session.ended_at = datetime.now(timezone.utc)
    await AuditService.record_event(
        db,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        session_id=db_session.session_id,
        event_type="session.terminated",
        details={"ended_at": str(db_session.ended_at)},
    )
    await db.commit()
    await db.refresh(db_session)
    
    return SessionCreateResponse(
        session_id=db_session.session_id,
        organization_id=db_session.organization_id,
        project_id=db_session.project_id,
        agent_id=db_session.agent_id,
        status=db_session.status,
        started_at=db_session.started_at
    )


@router.delete("")
@router.post("/clear")
async def clear_session_history(
    organization_id: Optional[str] = None,
    confirmation: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purge historical agent sessions. Only accessible by authenticated human operator."""
    if confirmation != "CONFIRM":
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
            return {"status": "cleared", "purged_count": 0}

    del_sessions = delete(AgentSessionModel).where(AgentSessionModel.organization_id.in_(target_org_ids))
    res = await db.execute(del_sessions)
    purged_count = res.rowcount or 0

    for org_id in target_org_ids:
        await AuditService.record_event(
            db,
            organization_id=org_id,
            event_type="sessions.history_cleared_by_human",
            severity="WARN",
            details={
                "operator": current_user.email or current_user.id,
                "purged_count": purged_count,
            },
        )

    await db.commit()
    return {
        "status": "cleared",
        "purged_count": purged_count,
        "message": f"Successfully cleared {purged_count} agent sessions.",
    }

