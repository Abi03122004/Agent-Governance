"""Organization and Multi-Tenant Service."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.organization import OrganizationModel


class OrganizationService:
    """Service layer for tenant management."""

    @staticmethod
    async def get_all(db: AsyncSession) -> List[OrganizationModel]:
        stmt = select(OrganizationModel)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_by_id(organization_id: str, db: AsyncSession) -> Optional[OrganizationModel]:
        stmt = select(OrganizationModel).where(OrganizationModel.id == organization_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create(organization_id: str, name: str, db: AsyncSession) -> OrganizationModel:
        org = OrganizationModel(id=organization_id, name=name, status="active")
        db.add(org)
        await db.commit()
        await db.refresh(org)
        return org
