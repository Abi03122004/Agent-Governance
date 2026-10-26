"""Agents and Credentials API Endpoints."""

import uuid
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import AgentModel, AgentCredentialModel, ProjectModel, MembershipModel, RuntimeActionModel, AgentSessionModel
from agent_security.domain.identity import AgentIdentity, AgentCredential, User
from agent_security.services.auth import generate_agent_credential
from agent_security.middleware.auth import get_current_user
from agent_security.services.audit_service import AuditService

router = APIRouter(prefix="/agents", tags=["Agents"])

async def _verify_agent_org_access(db: AsyncSession, organization_id: str, current_user: User):
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

class AgentCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    organization_id: str = Field(..., min_length=3, max_length=64)
    project_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    environment: str = Field(default="development", min_length=1, max_length=64)
    purpose: Optional[str] = Field(None, max_length=512)

class AgentUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(active|revoked|suspended)$")

class CredentialCreate(BaseModel):
    expires_in_seconds: Optional[int] = Field(None, gt=0)

class CredentialResponse(BaseModel):
    id: str
    plaintext_secret: str
    agent_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None

@router.post("", response_model=AgentIdentity, status_code=201)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _verify_agent_org_access(db, agent.organization_id, current_user)
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
    await db.flush()
    await AuditService.record_event(
        db,
        organization_id=db_agent.organization_id,
        project_id=db_agent.project_id,
        agent_id=db_agent.id,
        event_type="agent.created",
        details={"name": db_agent.name, "environment": db_agent.environment, "owner": db_agent.owner},
    )
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

from agent_security.middleware.auth import get_current_user, get_user_authorized_org_ids

@router.get("", response_model=List[AgentIdentity])
async def list_agents(organization_id: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if organization_id:
        await _verify_agent_org_access(db, organization_id, current_user)
        stmt = select(AgentModel).where(AgentModel.organization_id == organization_id)
    else:
        user_org_ids = await get_user_authorized_org_ids(db, current_user.id)
        if not user_org_ids:
            return []
        stmt = select(AgentModel).where(AgentModel.organization_id.in_(user_org_ids))
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
    await _verify_agent_org_access(db, a.organization_id, current_user)
        
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
    await _verify_agent_org_access(db, a.organization_id, current_user)
        
    a.status = update.status
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.status_updated",
        severity="WARN" if update.status in ["suspended", "revoked"] else "INFO",
        details={"status": update.status},
    )
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
async def create_credential(
    agent_id: str,
    payload: Optional[CredentialCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)
        
    plain_secret, hashed_secret = generate_agent_credential()
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=payload.expires_in_seconds)) if (payload and payload.expires_in_seconds) else None

    cred = AgentCredentialModel(
        id=f"cred_{uuid.uuid4().hex[:12]}",
        agent_id=a.id,
        secret_hash=hashed_secret,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(cred)
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.credential_created",
        details={"credential_id": cred.id, "expires_at": str(expires_at)},
    )
    await db.commit()
    await db.refresh(cred)
    
    return CredentialResponse(
        id=cred.id,
        plaintext_secret=plain_secret,
        agent_id=cred.agent_id,
        created_at=cred.created_at,
        expires_at=cred.expires_at,
    )

@router.post("/{agent_id}/credentials/rotate", response_model=CredentialResponse, status_code=201)
async def rotate_credential(
    agent_id: str,
    payload: Optional[CredentialCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    now = datetime.now(timezone.utc)
    # Revoke all existing active credentials for this agent
    active_creds_res = await db.execute(
        select(AgentCredentialModel).where(
            AgentCredentialModel.agent_id == agent_id,
            AgentCredentialModel.is_active == True,
        )
    )
    for c in active_creds_res.scalars().all():
        c.is_active = False
        c.revoked_at = now

    plain_secret, hashed_secret = generate_agent_credential()
    expires_at = (now + timedelta(seconds=payload.expires_in_seconds)) if (payload and payload.expires_in_seconds) else None

    new_cred = AgentCredentialModel(
        id=f"cred_{uuid.uuid4().hex[:12]}",
        agent_id=a.id,
        secret_hash=hashed_secret,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(new_cred)
    await AuditService.record_event(
        db,
        organization_id=a.organization_id,
        project_id=a.project_id,
        agent_id=a.id,
        event_type="agent.credential_rotated",
        details={"new_credential_id": new_cred.id, "expires_at": str(expires_at)},
    )
    await db.commit()
    await db.refresh(new_cred)

    return CredentialResponse(
        id=new_cred.id,
        plaintext_secret=plain_secret,
        agent_id=new_cred.agent_id,
        created_at=new_cred.created_at,
        expires_at=new_cred.expires_at,
    )

@router.post("/{agent_id}/credentials/{credential_id}/revoke", response_model=AgentCredential)
async def revoke_credential(agent_id: str, credential_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    a_res = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent_row = a_res.scalar_one_or_none()
    if not agent_row:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, agent_row.organization_id, current_user)

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
    await AuditService.record_event(
        db,
        organization_id=agent_row.organization_id,
        project_id=agent_row.project_id,
        agent_id=agent_id,
        event_type="agent.credential_revoked",
        severity="WARN",
        details={"credential_id": cred.id},
    )
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


@router.delete("/{agent_id}", status_code=200)
async def delete_agent(
    agent_id: str,
    rationale: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete an agent and its credentials. Only accessible by authenticated human operator."""
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    await _verify_agent_org_access(db, a.organization_id, current_user)

    org_id = a.organization_id
    proj_id = a.project_id
    agent_name = a.name

    # Clean up associated sessions and runtime actions
    await db.execute(delete(RuntimeActionModel).where(RuntimeActionModel.agent_id == agent_id))
    await db.execute(delete(AgentSessionModel).where(AgentSessionModel.agent_id == agent_id))

    # Delete the agent record (cascades credentials)
    await db.delete(a)
    await db.flush()

    await AuditService.record_event(
        db,
        organization_id=org_id,
        project_id=proj_id,
        agent_id=agent_id,
        event_type="agent.deleted_by_human",
        severity="WARN",
        details={
            "agent_id": agent_id,
            "name": agent_name,
            "operator": current_user.email or current_user.id,
            "action": "human_operator_agent_removal",
            "rationale": rationale or "Human Operator Authorized Purge",
        },
    )
    await db.commit()

    return {"status": "deleted", "agent_id": agent_id, "name": agent_name}


@router.post("/purge-inactive", status_code=200)
async def purge_inactive_agents(
    organization_id: Optional[str] = None,
    rationale: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purge all suspended or revoked agents within tenant scope. Only accessible by human operator."""
    if organization_id:
        await _verify_agent_org_access(db, organization_id, current_user)
        target_org_ids = [organization_id]
    else:
        target_org_ids = [m.organization_id for m in (await db.execute(select(MembershipModel).where(MembershipModel.user_id == current_user.id))).scalars().all()]

    inactive_agents_res = await db.execute(
        select(AgentModel).where(
            AgentModel.organization_id.in_(target_org_ids),
            AgentModel.status.in_(["suspended", "revoked"]),
        )
    )
    inactive_agents = inactive_agents_res.scalars().all()
    purged_ids = []

    for a in inactive_agents:
        purged_ids.append(a.id)
        await db.execute(delete(RuntimeActionModel).where(RuntimeActionModel.agent_id == a.id))
        await db.execute(delete(AgentSessionModel).where(AgentSessionModel.agent_id == a.id))
        await db.delete(a)

    if purged_ids:
        await db.flush()
        for org_id in target_org_ids:
            await AuditService.record_event(
                db,
                organization_id=org_id,
                event_type="agents.bulk_purged_by_human",
                severity="WARN",
                details={
                    "purged_count": len(purged_ids),
                    "purged_agent_ids": purged_ids,
                    "operator": current_user.email or current_user.id,
                    "rationale": rationale or "Human Operator Purge",
                },
            )
        await db.commit()

    return {"status": "purged", "count": len(purged_ids), "purged_agent_ids": purged_ids}

