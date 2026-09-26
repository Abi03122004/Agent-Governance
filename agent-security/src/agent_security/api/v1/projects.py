"""Projects API Endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import ProjectModel, OrganizationModel
from agent_security.domain.identity import Project

router = APIRouter(prefix="/projects", tags=["Projects"])

class ProjectCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    organization_id: str = Field(..., min_length=3, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)

@router.post("", response_model=Project, status_code=201)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    org_res = await db.execute(select(OrganizationModel).where(OrganizationModel.id == project.organization_id))
    if not org_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
        
    proj_res = await db.execute(select(ProjectModel).where(ProjectModel.id == project.id))
    if proj_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Project ID already exists")
        
    db_project = ProjectModel(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        status="active"
    )
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    
    return Project(
        id=db_project.id,
        organization_id=db_project.organization_id,
        name=db_project.name,
        status=db_project.status,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at
    )

@router.get("", response_model=List[Project])
async def list_projects(organization_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(ProjectModel)
    if organization_id:
        stmt = stmt.where(ProjectModel.organization_id == organization_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        Project(
            id=p.id,
            organization_id=p.organization_id,
            name=p.name,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in rows
    ]

@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProjectModel).where(ProjectModel.id == project_id))
    db_project = result.scalar_one_or_none()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return Project(
        id=db_project.id,
        organization_id=db_project.organization_id,
        name=db_project.name,
        status=db_project.status,
        created_at=db_project.created_at,
        updated_at=db_project.updated_at
    )
