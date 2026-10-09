"""Multi-Tenant Isolation and Authorization Guardrails."""

from agent_security.security.context import AuthenticatedAgent


def verify_tenant_boundary(
    agent: AuthenticatedAgent,
    target_organization_id: str,
) -> bool:
    """Ensure that an agent operates strictly within its tenant boundary."""
    return agent.organization_id == target_organization_id


def verify_agent_active(agent: AuthenticatedAgent) -> bool:
    """Check if the agent is in active status."""
    return agent.status.lower() == "active"
