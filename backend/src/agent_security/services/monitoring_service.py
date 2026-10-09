"""Monitoring and Observability Service."""

from typing import Any, Dict, List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_security.db.models.runtime_activity import RuntimeActionModel
from agent_security.db.models.agent import AgentModel
from agent_security.services.realtime import get_realtime_hub


class MonitoringService:
    """Service layer for real-time audit queries and stats."""

    @staticmethod
    async def get_stats(db: AsyncSession) -> Dict[str, int]:
        total_actions = (await db.execute(select(func.count(RuntimeActionModel.id)))).scalar_one() or 0
        allowed = (
            await db.execute(
                select(func.count(RuntimeActionModel.id)).where(RuntimeActionModel.decision == "ALLOW")
            )
        ).scalar_one() or 0
        blocked = (
            await db.execute(
                select(func.count(RuntimeActionModel.id)).where(RuntimeActionModel.decision == "BLOCK")
            )
        ).scalar_one() or 0
        pending_approval = (
            await db.execute(
                select(func.count(RuntimeActionModel.id)).where(
                    RuntimeActionModel.decision == "REQUIRE_APPROVAL"
                )
            )
        ).scalar_one() or 0
        suspended = (
            await db.execute(
                select(func.count(RuntimeActionModel.id)).where(RuntimeActionModel.decision == "SUSPEND")
            )
        ).scalar_one() or 0

        active_agents = (
            await db.execute(select(func.count(AgentModel.id)).where(AgentModel.status == "active"))
        ).scalar_one() or 0
        suspended_agents = (
            await db.execute(
                select(func.count(AgentModel.id)).where(AgentModel.status == "suspended")
            )
        ).scalar_one() or 0

        return {
            "active_agents": active_agents,
            "suspended_agents": suspended_agents,
            "actions_today": total_actions,
            "total_actions": total_actions,
            "allowed": allowed,
            "blocked": blocked,
            "pending_approval": pending_approval,
            "suspended": suspended,
        }

    @staticmethod
    async def get_recent_activity(db: AsyncSession, limit: int = 100) -> List[RuntimeActionModel]:
        stmt = (
            select(RuntimeActionModel)
            .order_by(RuntimeActionModel.created_at.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def broadcast_event(payload: Dict[str, Any]) -> None:
        hub = get_realtime_hub()
        await hub.broadcast(payload)
