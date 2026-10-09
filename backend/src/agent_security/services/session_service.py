"""Agent Runtime Session Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.session import AgentSessionModel


class SessionService:
    """Service layer for agent runtime sessions."""

    @staticmethod
    async def get_all(db: AsyncSession) -> List[AgentSessionModel]:
        stmt = select(AgentSessionModel)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_by_id(session_id: str, db: AsyncSession) -> Optional[AgentSessionModel]:
        stmt = select(AgentSessionModel).where(AgentSessionModel.session_id == session_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_session(
        organization_id: str,
        project_id: str,
        agent_id: str,
        credential_id: Optional[str],
        db: AsyncSession,
        session_id: Optional[str] = None,
    ) -> AgentSessionModel:
        sid = session_id or f"sess_{uuid.uuid4().hex[:16]}"
        session = AgentSessionModel(
            session_id=sid,
            organization_id=organization_id,
            project_id=project_id,
            agent_id=agent_id,
            credential_id=credential_id,
            status="active",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def terminate_session(session_id: str, db: AsyncSession) -> bool:
        stmt = (
            update(AgentSessionModel)
            .where(AgentSessionModel.session_id == session_id)
            .values(status="terminated", ended_at=datetime.now(timezone.utc))
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0
