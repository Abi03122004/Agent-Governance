"""Organizations API Endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import OrganizationModel
from agent_security.domain.identity import Organization

router = APIRouter(prefix="/organizations", tags=["Organizations"])

class OrganizationCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    name: str = Field(..., min_length=1, max_length=128)

@router.post("", response_model=Organization, status_code=201)
async def create_organization(org: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrganizationModel).where(OrganizationModel.id == org.id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization ID already exists")
        
    db_org = OrganizationModel(
        id=org.id,
        name=org.name,
        status="active"
    )
    db.add(db_org)
    await db.commit()
    await db.refresh(db_org)
    
    return Organization(
        id=db_org.id,
        name=db_org.name,
        status=db_org.status,
        created_at=db_org.created_at,
        updated_at=db_org.updated_at
    )

@router.get("", response_model=List[Organization])
async def list_organizations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrganizationModel))
    rows = result.scalars().all()
    return [
        Organization(
            id=o.id,
            name=o.name,
            status=o.status,
            created_at=o.created_at,
            updated_at=o.updated_at,
        )
        for o in rows
    ]

@router.get("/{org_id}", response_model=Organization)
async def get_organization(org_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrganizationModel).where(OrganizationModel.id == org_id))
    db_org = result.scalar_one_or_none()
    if not db_org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    return Organization(
        id=db_org.id,
        name=db_org.name,
        status=db_org.status,
        created_at=db_org.created_at,
        updated_at=db_org.updated_at
    )

from agent_security.services.audit_service import AuditService

class OrganizationUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(active|suspended)$")

@router.patch("/{org_id}", response_model=Organization)
async def update_organization_status(org_id: str, update_req: OrganizationUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrganizationModel).where(OrganizationModel.id == org_id))
    db_org = result.scalar_one_or_none()
    if not db_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    db_org.status = update_req.status
    await AuditService.record_event(
        db,
        organization_id=org_id,
        event_type="organization.status_updated",
        severity="WARN" if update_req.status == "suspended" else "INFO",
        details={"status": update_req.status},
    )
    await db.commit()
    await db.refresh(db_org)
    return Organization(
        id=db_org.id,
        name=db_org.name,
        status=db_org.status,
        created_at=db_org.created_at,
        updated_at=db_org.updated_at,
    )
