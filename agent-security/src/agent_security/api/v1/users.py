"""Users and Memberships API Endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from agent_security.db.session import get_db
from agent_security.db.models import UserModel, MembershipModel, OrganizationModel
from agent_security.domain.identity import User, Membership
from agent_security.middleware.auth import require_org_role, get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

class UserCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9\-_]+$")
    email: str = Field(..., min_length=3, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=128)

class MembershipCreate(BaseModel):
    id: str = Field(..., min_length=3, max_length=64)
    user_id: str = Field(..., min_length=3, max_length=64)
    organization_id: str = Field(..., min_length=3, max_length=64)
    role: str = Field(..., pattern=r"^(administrator|security_operator|approver|viewer)$")

@router.post("", response_model=User, status_code=201)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserModel).where((UserModel.id == user.id) | (UserModel.email == user.email))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User ID or Email already exists")
        
    db_user = UserModel(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status="active"
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return User(
        id=db_user.id,
        email=db_user.email,
        display_name=db_user.display_name,
        status=db_user.status,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at
    )

@router.get("", response_model=List[User])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel))
    rows = result.scalars().all()
    return [
        User(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            status=u.status,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in rows
    ]

@router.post("/memberships", response_model=Membership, status_code=201)
async def assign_role(membership: MembershipCreate, db: AsyncSession = Depends(get_db)):
    # Basic existence checks
    u_res = await db.execute(select(UserModel).where(UserModel.id == membership.user_id))
    if not u_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
        
    o_res = await db.execute(select(OrganizationModel).where(OrganizationModel.id == membership.organization_id))
    if not o_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
        
    m_res = await db.execute(select(MembershipModel).where(MembershipModel.id == membership.id))
    if m_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Membership ID already exists")
        
    db_mem = MembershipModel(
        id=membership.id,
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        role=membership.role
    )
    db.add(db_mem)
    await db.commit()
    await db.refresh(db_mem)
    
    return Membership(
        id=db_mem.id,
        user_id=db_mem.user_id,
        organization_id=db_mem.organization_id,
        role=db_mem.role,
        created_at=db_mem.created_at
    )
