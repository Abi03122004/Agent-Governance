"""Agents and Credentials API Endpoints."""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import AgentModel, AgentCredentialModel, ProjectModel
from agent_security.domain.identity import AgentIdentity, AgentCredential, User
from agent_security.services.auth import generate_agent_credential
from agent_security.middleware.auth import get_current_user

router = APIRouter(prefix="/agents", tags=["Agents"])

class AgentCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    organization_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    environment: str = Field(default="development", min_length=1, max_length=64)
    purpose: Optional[str] = Field(None, max_length=512)

class AgentUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(active|revoked|suspended)$")

class CredentialResponse(BaseModel):
    id: str
    plaintext_secret: str
    agent_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None

@router.post("", response_model=AgentIdentity, status_code=201)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Verify project exists and belongs to the specified organization
    p_res = await db.execute(
        select(ProjectModel).where(
            ProjectModel.id == agent.project_id,
            ProjectModel.organization_id == agent.organization_id
        )
    )
    if not p_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found or does not belong to organization")
        
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent.id))
    if a_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent ID already exists")
        
    db_agent = AgentModel(
        id=agent.id,
        organization_id=agent.organization_id,
        project_id=agent.project_id,
        name=agent.name,
        owner=current_user.email,
        environment=agent.environment,
        purpose=agent.purpose,
        status="active"
    )
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    
    return AgentIdentity(
        id=db_agent.id,
        organization_id=db_agent.organization_id,
        project_id=db_agent.project_id,
        name=db_agent.name,
        owner=db_agent.owner,
        environment=db_agent.environment,
        purpose=db_agent.purpose,
        status=db_agent.status,
        created_at=db_agent.created_at,
        updated_at=db_agent.updated_at
    )

@router.get("", response_model=List[AgentIdentity])
async def list_agents(organization_id: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(AgentModel)
    if organization_id:
        stmt = stmt.where(AgentModel.organization_id == organization_id)
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [
        AgentIdentity(
            id=a.id,
            organization_id=a.organization_id,
            project_id=a.project_id,
            name=a.name,
            owner=a.owner,
            environment=a.environment,
            purpose=a.purpose,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at
        ) for a in agents
    ]

@router.get("/{agent_id}", response_model=AgentIdentity)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    return AgentIdentity(
        id=a.id,
        organization_id=a.organization_id,
        project_id=a.project_id,
        name=a.name,
        owner=a.owner,
        environment=a.environment,
        purpose=a.purpose,
        status=a.status,
        created_at=a.created_at,
        updated_at=a.updated_at
    )

@router.patch("/{agent_id}", response_model=AgentIdentity)
async def update_agent_status(agent_id: str, update: AgentUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    a.status = update.status
    await db.commit()
    await db.refresh(a)
    
    return AgentIdentity(
        id=a.id,
        organization_id=a.organization_id,
        project_id=a.project_id,
        name=a.name,
        owner=a.owner,
        environment=a.environment,
        purpose=a.purpose,
        status=a.status,
        created_at=a.created_at,
        updated_at=a.updated_at
    )

@router.post("/{agent_id}/credentials", response_model=CredentialResponse, status_code=201)
async def create_credential(agent_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    plain_secret, hashed_secret = generate_agent_credential()
    
    cred = AgentCredentialModel(
        id=f"cred_{uuid.uuid4().hex[:12]}",
        agent_id=a.id,
        secret_hash=hashed_secret,
        is_active=True
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    
    return CredentialResponse(
        id=cred.id,
        plaintext_secret=plain_secret,
        agent_id=cred.agent_id,
        created_at=cred.created_at,
        expires_at=cred.expires_at
    )

@router.post("/{agent_id}/credentials/{credential_id}/revoke", response_model=AgentCredential)
async def revoke_credential(agent_id: str, credential_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(AgentCredentialModel).where(
            AgentCredentialModel.id == credential_id,
            AgentCredentialModel.agent_id == agent_id
        )
    )
    cred = result.scalar_one_or_none()
    
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
        
    cred.is_active = False
    cred.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cred)
    
    return AgentCredential(
        id=cred.id,
        agent_id=cred.agent_id,
        is_active=cred.is_active,
        created_at=cred.created_at,
        expires_at=cred.expires_at,
        revoked_at=cred.revoked_at
    )
