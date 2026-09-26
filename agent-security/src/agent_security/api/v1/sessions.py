"""Agent Sessions API Endpoints."""

import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import AgentSessionModel
from agent_security.domain.identity import AgentSession, AgentIdentity
from agent_security.middleware.auth import authenticate_agent

router = APIRouter(prefix="/sessions", tags=["Sessions"])

class SessionCreateResponse(BaseModel):
    session_id: str
    organization_id: str
    project_id: str
    agent_id: str
    status: str
    started_at: datetime

@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    correlation_id: Optional[str] = None, 
    db: AsyncSession = Depends(get_db), 
    agent: AgentIdentity = Depends(authenticate_agent)
):
    session_id = f"sess_{uuid.uuid4().hex}"
    
    db_session = AgentSessionModel(
        session_id=session_id,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        agent_id=agent.id,
        status="active",
        correlation_id=correlation_id
    )
    db.add(db_session)
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

@router.get("", response_model=List[SessionCreateResponse])
async def list_sessions(
    organization_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentSessionModel)
    if organization_id:
        stmt = stmt.where(AgentSessionModel.organization_id == organization_id)
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
            AgentSessionModel.agent_id == agent.id
        )
    )
    db_session = result.scalar_one_or_none()
    
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found or not owned by agent")
        
    db_session.status = "terminated"
    db_session.ended_at = datetime.now(timezone.utc)
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
