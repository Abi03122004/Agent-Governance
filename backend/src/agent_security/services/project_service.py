"""Project Service for Sandbox Management."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.project import ProjectModel


class ProjectService:
    """Service layer for project sandboxing."""

    @staticmethod
    async def get_by_org(organization_id: str, db: AsyncSession) -> List[ProjectModel]:
        stmt = select(ProjectModel).where(ProjectModel.organization_id == organization_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_by_id(project_id: str, db: AsyncSession) -> Optional[ProjectModel]:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create(project_id: str, organization_id: str, name: str, db: AsyncSession) -> ProjectModel:
        proj = ProjectModel(id=project_id, organization_id=organization_id, name=name, status="active")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)
        return proj
