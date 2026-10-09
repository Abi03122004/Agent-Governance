"""Authentication Services and Bearer Token Validation."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.session import AgentSessionModel
from agent_security.db.models.agent import AgentModel
from agent_security.security.context import AuthenticatedAgent


async def authenticate_session(
    session_token: str,
    db: AsyncSession,
) -> Optional[AuthenticatedAgent]:
    """Validate a session token and resolve the bound agent identity."""
    stmt = (
        select(AgentSessionModel, AgentModel)
        .join(AgentModel, AgentSessionModel.agent_id == AgentModel.id)
        .where(
            AgentSessionModel.session_id == session_token,
            AgentSessionModel.status == "active",
        )
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        return None

    session, agent = row
    return AuthenticatedAgent(
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        status=agent.status,
    )
