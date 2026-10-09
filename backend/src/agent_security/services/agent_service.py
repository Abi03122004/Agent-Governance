"""Agent Lifecycle and Registration Service."""

from typing import List, Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.agent import AgentModel
from agent_security.db.models.credential import AgentCredentialModel
from agent_security.security.credentials import generate_agent_credential


class AgentService:
    """Service layer for agent lifecycle and credential management."""

    @staticmethod
    async def get_all(db: AsyncSession) -> List[AgentModel]:
        stmt = select(AgentModel)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_by_id(agent_id: str, db: AsyncSession) -> Optional[AgentModel]:
        stmt = select(AgentModel).where(AgentModel.id == agent_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_agent(
        agent_id: str,
        organization_id: str,
        project_id: str,
        name: str,
        owner: str,
        environment: str,
        purpose: Optional[str],
        db: AsyncSession,
    ) -> AgentModel:
        agent = AgentModel(
            id=agent_id,
            organization_id=organization_id,
            project_id=project_id,
            name=name,
            owner=owner,
            environment=environment,
            purpose=purpose,
            status="active",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def issue_credentials(agent_id: str, db: AsyncSession) -> Tuple[str, str]:
        """Issue high-entropy credentials for an agent. Returns (credential_id, plaintext_token)."""
        plaintext, secret_hash = generate_agent_credential()
        import uuid
        cred_id = f"cred_{uuid.uuid4().hex[:16]}"
        cred = AgentCredentialModel(
            id=cred_id,
            agent_id=agent_id,
            secret_hash=secret_hash,
            is_active=True,
        )
        db.add(cred)
        await db.commit()
        return cred_id, plaintext

    @staticmethod
    async def set_status(agent_id: str, status: str, db: AsyncSession) -> bool:
        stmt = update(AgentModel).where(AgentModel.id == agent_id).values(status=status)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0
